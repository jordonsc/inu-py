import asyncio
import logging

from .cmd import server as s_cmd
from .. import error
from ..util.asynchronous import TaskPool


class MessageHandler:
    def __init__(self):
        self.base_logger = logging.getLogger('mnats.proto')
        self.verbose_cmd_logging = False

    async def on_info(self, info: s_cmd.Info):
        if self.verbose_cmd_logging:
            self.base_logger.debug(f"INFO: {info.get_info()}")

    async def on_ok(self, ok: s_cmd.OK):
        if self.verbose_cmd_logging:
            self.base_logger.debug("OK")

    async def on_error(self, err: s_cmd.Error):
        if self.verbose_cmd_logging:
            self.base_logger.debug(f"ERR: {err.get_error()}")

    async def on_ping(self, ping: s_cmd.Ping):
        if self.verbose_cmd_logging:
            self.base_logger.debug("PING")

    async def on_pong(self, pong: s_cmd.Pong):
        if self.verbose_cmd_logging:
            self.base_logger.debug("PONG")

    async def on_msg(self, msg: s_cmd.Message):
        if self.verbose_cmd_logging:
            self.base_logger.debug(f"MSG: ({msg.get_sid()}) {msg.get_subject().decode()}: {msg.get_payload().decode()}")

    async def on_hmsg(self, hmsg: s_cmd.HeaderMessage):
        if self.verbose_cmd_logging:
            self.base_logger.debug(
                f"HMSG: ({hmsg.get_sid()}) {hmsg.get_subject().decode()}: [{hmsg.get_headers().decode()}] // " +
                f"{hmsg.get_payload().decode()}"
            )


class Parser:
    MSG_CLASSES = [s_cmd.Message, s_cmd.HeaderMessage, s_cmd.OK, s_cmd.Error, s_cmd.Info, s_cmd.Ping, s_cmd.Pong]
    MIN_MESSAGE_SIZE = 5

    def __init__(self, handler: MessageHandler):
        self.logger = logging.getLogger("mnats.proto.parser")
        self.buf = bytearray()
        self.handler = handler
        self.tasks = TaskPool()

    async def parse(self, data: bytes):
        """
        Append data to buffer and process.
        """
        self.buf.extend(data)

        while len(self.buf) >= self.MIN_MESSAGE_SIZE:
            if not await self.parse_data():
                break

    async def parse_data(self) -> bool:
        """
        Looks for a message in the current buffer.

        Will process a message if it deems it valid, and advance the buffer.
        Returns True if a message was processed.
        """
        for cls in self.MSG_CLASSES:
            if not cls.is_match(self.buf):
                continue

            command = None
            try:
                # Parse the message & dispatch to appropriate callbacks
                command = cls(self.buf)
                try:
                    await self.process_message(command)
                except Exception as e:
                    raise error.ProtocolError(
                        f"Error processing cmd '{cls.get_cmd().decode()}' - {type(e).__name__}: {e}"
                    )

                return True

            except error.IncompletePayload:
                # Assume the entire message hasn't been sent yet.
                # This WILL happen on MSG packets as we're using `readline()` on the stream.
                return False

            except error.ParseError as e:
                raise e

            except Exception as e:
                raise error.ProtocolError(f"Error during message parsing: {e}")

            finally:
                # Advance position in buffer to the end of this message
                if command and command.consumed():
                    self.buf = self.buf[command.consumed():]

        return False

    async def process_message(self, command: cmd.Command):
        """
        Execute callbacks relevant to the current message.
        """
        if command is None:
            self.logger.error("Attempted to process null message")
            return

        if isinstance(command, s_cmd.OK):
            self.tasks.run(self.handler.on_ok(command))
        elif isinstance(command, s_cmd.Error):
            self.tasks.run(self.handler.on_error(command))
        elif isinstance(command, s_cmd.Info):
            self.tasks.run(self.handler.on_info(command))
        elif isinstance(command, s_cmd.Ping):
            self.tasks.run(self.handler.on_ping(command))
        elif isinstance(command, s_cmd.Pong):
            self.tasks.run(self.handler.on_pong(command))
        elif isinstance(command, s_cmd.Message):
            self.tasks.run(self.handler.on_msg(command))
        elif isinstance(command, s_cmd.HeaderMessage):
            self.tasks.run(self.handler.on_hmsg(command))
        else:
            self.logger.error(f"Unimplemented command message: {command.__class__}")

        await asyncio.sleep(0)
