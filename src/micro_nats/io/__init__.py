import asyncio
import logging

from .. import protocol, model, error
from ..protocol.cmd import client as c_cmd
from ..util.asynchronous import TaskPool


class IoHandler:
    """
    A base class that offers optional functions to override which will be executed on IO events.
    """

    async def on_connect(self, server: model.ServerInfo):
        pass

    async def on_disconnect(self):
        pass


class IoClient:
    """
    Manages a live TCP connection to a NATS server.
    """

    def __init__(self, r_stream: asyncio.StreamReader, w_stream: asyncio.StreamWriter,
                 msg_handler: protocol.MessageHandler, on_disconnect: callable):
        super().__init__()

        self.logger = logging.getLogger('mnats.io.client')
        self.read_stream = r_stream
        self.write_stream = w_stream
        self.parser = protocol.Parser(msg_handler)
        self.on_disconnect = on_disconnect
        self.pool = TaskPool()

        self.verbose_logging = False

        async def read_task():
            """
            Indefinite read loop
            """
            cpy = hasattr(self.read_stream, "at_eof")
            while self.is_connected():
                await asyncio.sleep(0)

                if cpy and self.read_stream.at_eof():
                    self.logger.warning("Connection terminated by remote")
                    await self.close()
                    self.pool.run(self.on_disconnect())
                    break

                try:
                    line = await self.read_stream.readline()
                    if self.verbose_logging:
                        self.logger.debug(f"<<< {line}")
                    await self.parser.parse(line)

                except OSError:
                    self.logger.warning(f"Connection reset (read)")
                    await self.close()
                    self.pool.run(self.on_disconnect())

                except asyncio.CancelledError:
                    await self.close()
                    break

                except Exception as e:
                    self.logger.error(f"IO fault: {type(e)}: {e}")

        self.pool.run(read_task())

    async def close(self):
        """
        Drain streams and disconnect.
        """
        try:
            if self.write_stream:
                self.logger.info("Closing connection")
                await self.write_stream.drain()
                self.write_stream.close()

        except OSError:
            # Can happen if you called `close()` to clean things up during a disconnect
            pass

        except Exception as e:
            self.logger.warning(f"Error trying to close stream: {type(e)}: {e}")

        finally:
            self.read_stream = None
            self.write_stream = None

    def is_connected(self):
        """
        Returns True if a connection is open to a remote NATS server.
        """
        if hasattr(self.write_stream, "is_closing"):
            # CPython
            return self.read_stream is not None and self.write_stream is not None and not self.write_stream.is_closing()
        else:
            # MPy
            return self.read_stream is not None and self.write_stream is not None

    def is_closing(self):
        """
        Returns True if the write stream is preparing to close.
        """
        if not hasattr(self.write_stream, "is_closing"):
            return False

        return self.write_stream is not None and self.write_stream.is_closing()

    def is_closed(self):
        """
        Check if the connection is fully closed and this object is now defunct.
        """
        return self.read_stream is None and self.write_stream is None

    async def send(self, cmd: c_cmd.ClientCommand, flush: bool = True, wait: bool = False):
        """
        Send a ClientCommand to the server.

        If `flush` is set to True, the WriteStream will be immediately flushed.
        If `wait` is set to True, this function will block until the WriteStream has been flushed.
        """
        if wait:
            await self.write(cmd.marshal(), flush=flush)
        else:
            self.pool.run(self.write(cmd.marshal(), flush=flush))

    async def write(self, data: bytes, flush: bool = True):
        """
        Write raw data to the server stream.

        If not connected, will wait until `timeout` for the connection to come alive before throwing a
        `NoConnectionError` exception.
        """
        if not self.is_connected():
            raise error.NoConnectionError()

        if self.verbose_logging:
            self.logger.debug(f">>> {data}")

        self.write_stream.write(data)

        if flush:
            await self.write_stream.drain()
