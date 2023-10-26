import logging

from . import model, error
from .io.manager import IoManager, IoHandler, SubManager
from .protocol.cmd import client as c_cmd
from .util.asynchronous import TaskPool


class Client:
    def __init__(self, ctx: model.ServerContext, handler: IoHandler | None = None):
        self.logger = logging.getLogger('mnats.client')
        self.manager = IoManager(ctx, handler=handler)
        self.sub_mgr = SubManager()
        self.pool = TaskPool()

    def update_context(self, ctx: model.ServerContext):
        """
        Add a new server context, removing the existing.

        NB: this will not reconnect the server or modify the existing handshake.
        If disconnected and reconnected, it will use the new context
        """
        self.manager.context = ctx

    def get_connection_state(self) -> int:
        """
        Returns a value in `IoManager.ConnectionState`.
        """
        return self.manager.state

    def is_connected(self) -> bool:
        return self.manager.state == self.manager.ConnectionState.CONNECTED

    async def connect(self):
        """
        Connect to the next NATS server in the server list.
        """
        await self.manager.connect()

    async def disconnect(self):
        """
        Disconnect from remote server.
        """
        await self.manager.disconnect()

    def get_server_info(self) -> model.ServerInfo | None:
        """
        Returns a ServerInfo object if we're connected to a server.
        """
        return self.manager.server_info

    def jetstream_supported(self) -> bool:
        """
        Check if the server supports Jetstream.
        """
        return self.manager.server_info and self.manager.server_info.jetstream

    async def publish(self, subject: str | bytes, payload: str | bytes | None = None, reply_to: str | bytes = None,
                      wait: bool = False):
        """
        Publish a Core NATS message.

        If `wait` is set to True, this function will block until the stream is flushed.
        """
        await self.manager.safe_send(c_cmd.Pub(subject=subject, payload=payload, reply_to=reply_to), wait=wait)

    async def subscribe(self, subject: str | bytes, cb: callable, queue_grp: str | bytes | None = None) -> str:
        """
        Subscribe to a Core NATS subject.

        Returns the subscription ID. Callback should have the signature:
            async cb(model.Message) -> None
        """
        sub_id = self.sub_mgr.generate_core_sub_id()
        await self.manager.safe_send(c_cmd.Sub(subject=subject, queue_grp=queue_grp, sid=sub_id))
        self.manager.bind_callback(sub_id, callback=cb)
        return sub_id

    async def unsubscribe(self, sid: str | bytes, max_messages: int | None = None):
        """
        Unsubscribe from a NATS Core subject by providing the subscription ID (sid) returned from `subscribe()`.

        If `max_messages` is provided, the subscription will end after `max_messages` messages has been received.
        """
        if max_messages is None:
            # Unless we track this on the client, we don't really know when the sub is done. Thus, rampant use of
            # `max_messages` will create a memory leak.
            try:
                self.manager.unbind_callback(sid)
            except error.NotFoundError:
                pass

        if self.is_connected():
            await self.manager.safe_send(c_cmd.Unsub(sid=sid, max_messages=max_messages))
