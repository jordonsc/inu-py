import logging

from . import protocol
from .io.manager import JetstreamManager, SubManager
from .io.manager.consumer import ConsumerManager
from .io.manager.message import MessageManager
from .io.manager.stream import StreamManager
from .protocol.server import ServerStats
from ..client import Client as NatsClient
from ..util import asynchronous


class Client(SubManager):
    def __init__(self, nats_client: NatsClient):
        self.nats_client = nats_client
        self.manager = JetstreamManager(nats_client)
        self.logger = logging.getLogger('mnats.js.client')
        self.pool = asynchronous.TaskPool()

        super().__init__(self.manager)

        # Primary means of interacting with APIs
        self.stream = StreamManager(self.manager)
        self.consumer = ConsumerManager(self.manager)
        self.msg = MessageManager(self.manager)

    async def flush_inbox(self):
        """
        Flushes the inbox of all push listeners.

        Call this if you've disconnected/reconnected the NATS server, or have flushed your consumers.
        """
        await self.manager.inbox_mgr.flush()

    def set_io_timeout(self, timeout: float):
        """
        Set the timeout for standard request-response transactions.
        """
        self.manager.io_timeout = timeout

    async def stats(self, on_done: callable = None) -> ServerStats:
        """
        Get into from the server about limits and account usage.
        """

        async def fn():
            msg = await self.manager.request(protocol.API.get(protocol.API.INFO, timeout=self.manager.io_timeout))
            return protocol.from_msg(msg)

        return await self._run_or_await(fn, on_done)
