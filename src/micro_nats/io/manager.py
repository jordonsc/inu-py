import asyncio
import logging
import time

from . import IoHandler, IoClient
from .. import model, error, protocol
from ..protocol.cmd import server as s_cmd, client as c_cmd
from ..util import uri
from ..util.asynchronous import TaskPool


class SubManager:
    """
    Subscription ID list. Use for SUB commands.
    """

    def __init__(self):
        self.sub_index = 0

    def generated_count(self) -> int:
        return self.sub_index

    def generate_core_sub_id(self) -> str:
        """
        Return a new ID for a Core NATS subscription.
        """
        self.sub_index += 1
        return f"C{self.sub_index}"


class IoManager(protocol.MessageHandler):
    """
    Extend this class to add NATS connectivity to your class.
    """

    class ConnectionState:
        CLOSED = 0
        HANDSHAKE = 1
        CONNECTED = 2
        CLOSING = 3

    def __init__(self, ctx: model.ServerContext, handler: IoHandler = None):
        super().__init__()

        self.logger = logging.getLogger('mnats.io.manager')
        self.io: IoClient | None = None
        self.context = ctx
        self.handler = handler or IoHandler()
        self.state = self.ConnectionState.CLOSED
        self.server_info: model.ServerInfo | None = None
        self.ping_counter = 0
        self.ping_timer = time.time()
        self.ping_task = None
        self.callbacks = {}
        self.pool = TaskPool()

        self.verbose_cmd_logging = False
        self.has_chaos = True  # set to false to have simulated disconnects every 15 seconds

    async def connect(self):
        """
        Establish a connection to the NATS server.

        Will take the next server off the ServerContext.servers list and cycle them.
        Will disconnect any existing connection.
        """
        await self.disconnect()

        server = uri.parse_server(self.context.get_server(cycle=True))

        while True:
            try:
                self.logger.info(f"Opening connection to {server.address}:{server.port}..")
                self.io = IoClient(*await asyncio.wait_for(
                    asyncio.open_connection(server.address, server.port),
                    self.context.connect_timeout
                ), msg_handler=self, on_disconnect=self.on_connection_reset)

                self.state = self.ConnectionState.HANDSHAKE
                self.logger.debug("NATS connection established")

                if not self.has_chaos:
                    async def chaos():
                        last_kill = time.time()
                        while True:
                            if not self.io.is_connected():
                                last_kill = time.time()
                            elif time.time() - last_kill >= 15:
                                self.logger.warning("Chaos kill")
                                await self.on_connection_reset()
                                last_kill = time.time()

                            await asyncio.sleep(1)

                    self.logger.warning("Starting chaos daemon")
                    self.pool.run(chaos())
                    self.has_chaos = True

                break

            except asyncio.TimeoutError:
                if self.context.auto_reconnect:
                    self.logger.error("Connection timeout")
                else:
                    raise error.NetworkTimeout()

            except OSError:
                if self.context.auto_reconnect:
                    self.logger.error("Connection refused")
                else:
                    raise error.ConnectionRefused()

            await asyncio.sleep(self.context.reconnect_delay)

    async def on_connection_reset(self):
        """
        ClientIO disconnect or ping timeout.

        IMPORTANT: call disconnect() to fire disconnect callbacks which will clean up consumers.
        If permitted, the connection will be reconnected and the connect() callback will recreate consumers.
        """
        await self.disconnect()

        if self.context.auto_reconnect:
            await self.connect()

    async def handshake(self):
        """
        Establishes a client session with a connected server.

        Once we have the server's INFO message, we can begin the connect handshake by sending back a CONNECT message.
        This will do nothing outside of the HANDSHAKE phase, and must have a hydrated ServerInfo object first.
        """
        if self.state != self.ConnectionState.HANDSHAKE or self.server_info is None:
            raise error.MicroNatsError(f"Cannot handshake at this point: state: {self.state}; server_info: {self.server_info}")

        connect = c_cmd.Connect(
            verbose=False,
            pedantic=True,
            tls_required=False,
            lang=model.CLIENT_LANGUAGE,
            version=model.CLIENT_VERSION,
            protocol=0,
            headers=True,
        )

        if self.context.client_name:
            connect.name = self.context.client_name
        if self.context.auth_token:
            connect.auth_token = self.context.auth_token
        if self.context.auth_user:
            connect.user = self.context.auth_user
        if self.context.auth_pass:
            connect.password = self.context.auth_pass
        if self.context.auth_jwt:
            connect.jwt = self.context.auth_jwt
        if self.context.auth_nkey:
            connect.nkey = self.context.auth_nkey

        await self.io.write(connect.marshal())
        self.state = self.ConnectionState.CONNECTED

        # Handshake is complete here, so now we'll set up a pinger
        self.ping_timer = time.time()

        async def ping_task():
            try:
                while self.state == self.ConnectionState.CONNECTED:
                    await asyncio.sleep(1)

                    if time.time() - self.ping_timer > self.context.ping_interval:
                        self.ping_counter += 1
                        await self.safe_write(c_cmd.Ping().marshal(), flush=True)
                        self.ping_timer = time.time()
                        continue

                    if self.ping_counter > self.context.max_missed_pings:
                        self.logger.error("Ping timeout")
                        await self.on_connection_reset()

            except asyncio.CancelledError:
                self.logger.debug("Pinger cancelled")

        self.ping_task = asyncio.create_task(ping_task())

        # All wrapped up - exec connect callback
        self.pool.run(self.handler.on_connect(server=self.server_info))

    async def disconnect(self):
        """
        Drain streams and disconnect.
        """
        if self.ping_task:
            self.ping_task.cancel()
            await asyncio.sleep(0)
            self.ping_task = None

        if self.io:
            self.state = self.ConnectionState.CLOSING
            await self.io.close()
            self.io = None
            self.pool.run(self.handler.on_disconnect())

        self.state = self.ConnectionState.CLOSED

    def bind_callback(self, sid: str, callback: callable):
        """
        Binds a callback to an SID.

        Callback should have signature:
            async (model.Server) -> None
        """
        if sid in self.callbacks:
            raise error.AlreadyExistsError(f"A callback is already bound for SID {sid}")

        self.callbacks[sid] = callback

    def unbind_callback(self, sid: str):
        """
        Unbinds an SID from a callback.
        """
        if sid not in self.callbacks:
            raise error.NotFoundError(f"SID {sid} does not have a registered callback")

        del self.callbacks[sid]

    def on_traffic(self):
        """
        Acknowledges that we've received data from the server, belaying the need to send a ping.
        """
        self.ping_timer = time.time()

    async def on_info(self, info: s_cmd.Info):
        await super().on_info(info)
        self.on_traffic()

        if self.state == self.ConnectionState.HANDSHAKE:
            svr_info = model.ServerInfo.from_info(info)

            # Validate we have key mandatory fields from the server before using this as the server info -
            if svr_info.server_name and svr_info.version and svr_info.proto and svr_info.max_payload:
                self.server_info = svr_info
                self.pool.run(self.handshake())
            else:
                self.logger.warning("Appear to have incomplete server info message")

    async def on_ok(self, ok: s_cmd.OK):
        await super().on_ok(ok)
        self.on_traffic()

    async def on_error(self, err: s_cmd.Error):
        await super().on_error(err)
        self.on_traffic()
        self.logger.error(f"NATS error: {err.get_error()}")

    async def on_ping(self, ping: s_cmd.Ping):
        await super().on_ping(ping)
        self.on_traffic()
        self.pool.run(self.safe_write(c_cmd.Pong().marshal()))

    async def on_pong(self, pong: s_cmd.Pong):
        await super().on_pong(pong)
        self.on_traffic()
        self.ping_counter -= 1

    async def on_msg(self, msg: s_cmd.Message):
        await super().on_msg(msg)
        self.on_traffic()

        if msg.get_sid() in self.callbacks:
            await self.callbacks[msg.get_sid()](model.Message(msg))

    async def on_hmsg(self, hmsg: s_cmd.HeaderMessage):
        await super().on_hmsg(hmsg)
        self.on_traffic()

        if hmsg.get_sid() in self.callbacks:
            await self.callbacks[hmsg.get_sid()](model.Message(hmsg))

    async def safe_send(self, payload: c_cmd.ClientCommand, flush=True, wait=False, timeout: float = 5,
                        retries: int = 5):
        """
        Attempts to send a command, retrying or waiting for a connection if it was not available at the immediate
        time of the call.
        """
        if wait:
            await self.safe_write(payload.marshal(), flush=flush, timeout=timeout, retries=retries)
        else:
            self.pool.run(self.safe_write(payload.marshal(), flush=flush, timeout=timeout, retries=retries))

    async def safe_write(self, payload: bytes, flush=True, timeout: float = 5, retries: int = 5):
        """
        Attempts to write raw data, retrying or waiting for a connection if it was not available at the immediate
        time of the call.
        """
        attempts = 0
        while attempts < retries:
            try:
                start_time = time.time()
                while self.state != self.ConnectionState.CONNECTED:
                    if time.time() - start_time > timeout:
                        raise error.NoConnectionError()

                    await asyncio.sleep(0.001)

                await self.io.write(payload, flush=flush)
                return

            except OSError:
                pass
            except error.NoConnectionError:
                pass

            attempts += 1
