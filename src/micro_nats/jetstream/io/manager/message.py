from micro_nats.jetstream import protocol
from micro_nats.jetstream.io.manager import SubManager
from micro_nats.jetstream.protocol import ack
from micro_nats.jetstream.protocol import consumer, stream
from micro_nats.model import Message
from micro_nats.util import Time


class MessageManager(SubManager):
    async def ack(self, msg: Message):
        """
        Ack's a message, asynchronously.
        """
        self.manager.ensure_connected_and_ackable(msg)
        await self.manager.client.publish(msg.get_reply_to(), wait=False)

    async def nack(self, msg: Message, delay: float = None):
        """
        Nack's a message, asynchronously.

        If `delay` is provided, the redelivery of the message will be delayed by `delay` seconds.
        """
        self.manager.ensure_connected_and_ackable(msg)
        await self.manager.client.publish(msg.get_reply_to(), payload=ack.Nak(delay=delay).marshal(), wait=False)

    async def in_progress(self, msg: Message):
        """
        Informs the Jetstream server that this message is a work-in-progress and resets the ack-retry delay.

        May be used multiple times.
        """
        self.manager.ensure_connected_and_ackable(msg)
        await self.manager.client.publish(msg.get_reply_to(), payload=ack.InProgress().marshal(), wait=False)

    async def term(self, msg: Message):
        """
        Informs the Jetstream server that this message is unprocessable and not to resend it.
        """
        self.manager.ensure_connected_and_ackable(msg)
        await self.manager.client.publish(msg.get_reply_to(), payload=ack.Term().marshal(), wait=False)

    async def get_last(self, stream_name: str, subject: str, on_done: callable = None) -> Message:
        """
        A non-consumer call to get the last message in a stream for a given subject.
        """

        async def fn():
            req = {"last_by_subj": subject}
            msg = await self.manager.request(
                protocol.API.get(protocol.API.STREAM_MSG_GET, stream=stream_name),
                payload=self._as_json(req), timeout=self.manager.io_timeout
            )
            return Message.from_stream(protocol.from_msg(msg))

        return await self._run_or_await(fn, on_done)

    async def get_seq(self, stream_name: str, sequence: int, on_done: callable = None) -> Message:
        """
        A non-consumer call to get a specific message in a stream by its sequence number
        """
        assert sequence > 0, "Sequence must be a positive integer"

        async def fn():
            req = {"seq": sequence}
            msg = await self.manager.request(
                protocol.API.get(protocol.API.STREAM_MSG_GET, stream=stream_name),
                payload=self._as_json(req), timeout=self.manager.io_timeout
            )
            return Message.from_stream(protocol.from_msg(msg))

        return await self._run_or_await(fn, on_done)

    async def delete(self, stream_name: str, sequence: int, on_done: callable = None) -> stream.MessageDeleteResponse:
        """
        Delete a specific message.
        """
        assert sequence > 0, "Sequence must be a positive integer"

        async def fn():
            req = {"seq": sequence}
            return protocol.from_msg(await self.manager.request(
                protocol.API.get(protocol.API.STREAM_MSG_DEL, stream=stream_name),
                payload=self._as_json(req), timeout=self.manager.io_timeout
            ))

        return await self._run_or_await(fn, on_done)

    async def fetch(self, cons: consumer.Consumer, timeout: float = 0, on_done: callable = None) -> Message:
        """
        Synchronously fetch the next message from a pull consumer.

        See notes in `fetch_batch()` on using a timeout value.
        """

        async def fn():
            nonlocal timeout

            req = {'batch': 1}

            if timeout == -1:
                req['no_wait'] = True
                timeout = 0
            elif timeout > 0:
                # expires is the time in which the server will throw a 408
                req['expires'] = Time.sec_to_nano(timeout)
                # timeout is the time in which the client will drop out
                timeout = timeout + 1
                # we should let the server drop first, so we don't miss any messages that occur after we stop listening
                # but before the server has timed out

            return await self.manager.request(protocol.API.get(
                protocol.API.CONSUMER_MSG_NEXT, stream=cons.stream_name, consumer=cons.consumer_cfg.name
            ), payload=self._as_json(req), timeout=timeout)

        return await self._run_or_await(fn, on_done)

    async def fetch_batch(self, cons: consumer.Consumer, batch: int = 5, timeout: float = 0):
        """
        Fetch a batch of messages from a pull-based consumer, yielding as they're received.

        Set timeout to 0 to run without a timeout, until max_messages is reached.
        Set timeout to -1 to use `no_wait` mode, where the request will instantly fail if there are no new messages.

        NB: If you use a timeout and the last call to `fetch()` did hit the timeout, further calls will fail until the
        client is reconnected.

        Returns `Generator[Message]`
        """
        req = {'batch': batch}

        if timeout == -1:
            req['no_wait'] = True
            timeout = 0
        elif timeout > 0:
            # expires is the time in which the server will throw a 408
            req['expires'] = Time.sec_to_nano(timeout)
            # timeout is the time in which the client will drop out
            timeout = timeout + 1
            # we should let the server drop first, so we don't miss any messages that occur after we stop listening
            # but before the server has timed out

        async for msg in self.manager.request_many(protocol.API.get(
                protocol.API.CONSUMER_MSG_NEXT, stream=cons.stream_name, consumer=cons.consumer_cfg.name
        ), payload=self._as_json(req), max_msgs=batch, timeout=timeout):
            yield msg
