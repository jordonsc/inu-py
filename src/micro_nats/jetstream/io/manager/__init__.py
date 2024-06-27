import asyncio
import json
import logging
import time

from ..inbox import InboxManager
from ... import error as js_error, protocol
from ...protocol import ErrorResponse
from .... import error
from ....client import Client as NatsClient
from ....model import Message
from ....util import asynchronous
from ....util.asynchronous import TaskPool


class JetstreamManager:
    def __init__(self, client: NatsClient):
        self.client = client
        self.inbox_mgr = InboxManager(self.client)
        self.logger = logging.getLogger('mnats.js.mgr')
        self.pool = asynchronous.TaskPool()

        self.io_timeout: float = 30

    def ensure_connected(self):
        if not self.client.is_connected():
            raise error.NoConnectionError()

    def ensure_connected_and_ackable(self, msg: Message):
        self.ensure_connected()
        if not msg.can_ack():
            raise js_error.NotAckable(str(msg))

    async def request(self, api: str, payload: bytes | str = b'', timeout: float = 5) -> Message:
        """
        Synchronous single request-response message, using an ephemeral inbox to capture a single-message response.

        Blocks until message is received or timeout reached.
        """
        self.ensure_connected()

        future = asynchronous.Future()
        inbox = await self.inbox_mgr.get_inbox(future.cb)

        try:
            await self.client.publish(subject=api, payload=payload, reply_to=inbox)

            start_time = time.time()
            while not future.done():
                await asyncio.sleep(0.001)
                if timeout and (time.time() - start_time >= timeout):
                    raise error.NetworkTimeout(f"Timeout waiting for reply ({timeout} seconds)")

            msg: Message = future.result

            if msg.status_code() == 404:
                raise error.NotSupported("No messages")
            elif msg.status_code() == 408:
                raise error.NetworkTimeout("Request timeout (408)")
            elif msg.status_code() >= 400:
                raise error.RequestRefused(msg.status_description())

            return msg
        finally:
            await self.inbox_mgr.free_inbox(inbox)

    async def request_many(self, api: str, payload: bytes | str, max_msgs: int = 1, timeout: float = 0):
        """
        Generator request-response message handler using an inbox to read responses.

        Exits yield loop when a timeout or >=400 status is received. Inbox will be burnt on timeout/completion.

        Usage:
            async for x in manager.request_many(..):
                x.get_payload()
        """
        self.ensure_connected()

        count = 0
        exit_flag = False
        messages = []

        async def on_msg(msg: Message):
            nonlocal exit_flag, messages, count

            # Status 408 sent when server hits expiry, or 404 for no messages
            if msg.status_code() >= 400:
                exit_flag = True
                return

            messages.append(msg)

        inbox = await self.inbox_mgr.get_inbox(on_msg)
        start_time = time.time()

        try:
            await self.client.publish(subject=api, payload=payload, reply_to=inbox)

            # exit_flag is set by the callback detecting a >= 400 status code (server timeout/error)
            while not exit_flag:
                while len(messages):
                    yield messages.pop(0)
                    count += 1
                    if count >= max_msgs:
                        return

                if timeout and (time.time() - start_time >= timeout):
                    break

                await asyncio.sleep(0.001)

        except Exception as e:
            raise e

        finally:
            # Inbox must be destroyed in the event an "expires" was sent to the server and it returned a 408.
            # If it's not burnt, it will be reused and would be considered defunct in the server's eyes.
            await self.inbox_mgr.free_inbox(inbox, destroy=True)


class SubManager:
    def __init__(self, js_mgr: JetstreamManager):
        self.manager = js_mgr
        self.pool = TaskPool()
        self.logger = logging.getLogger('mnats.js.mgr')

    @staticmethod
    def _as_json(data: dict) -> bytes:
        return json.dumps(data).encode()

    async def _run_or_await(self, coro, on_done: callable = None):
        async def fn():
            try:
                resp = await coro()
            except Exception as e:
                resp = protocol.from_exception(e)

            self.pool.run(on_done(resp))

        if on_done:
            self.pool.run(fn())
            return None
        else:
            r = await coro()
            if isinstance(r, ErrorResponse):
                if r.code == 404:
                    raise error.NotFoundError(r.description)
                elif r.code == 408:
                    raise error.NetworkTimeout(r.description)
                else:
                    raise js_error.ErrorResponseException(r)
            return r
