from micro_nats import error
from micro_nats.jetstream import protocol
from micro_nats.jetstream.io.manager import SubManager, JetstreamManager
from micro_nats.jetstream.protocol import consumer


class ConsumerManager(SubManager):
    def __init__(self, js_mgr: JetstreamManager):
        super().__init__(js_mgr)
        self.consumer_map = {}

    async def info(self, stream_name: str, consumer_name: str, on_done: callable = None) -> consumer.ConsumerInfo:
        """
        Returns details on a consumer.
        """

        async def fn():
            return protocol.from_msg(await self.manager.request(
                protocol.API.get(protocol.API.CONSUMER_INFO, stream=stream_name, consumer=consumer_name),
                timeout=self.manager.io_timeout
            ))

        return await self._run_or_await(fn, on_done)

    async def listing(self, stream_name: str, offset: int = 0, on_done: callable = None) -> list[consumer.ConsumerInfo]:
        """
        Provides a list of consumers.
        """

        async def fn():
            payload = {'offset': offset}

            msg = await self.manager.request(
                protocol.API.get(protocol.API.CONSUMER_LIST, stream=stream_name), payload=self._as_json(payload),
                timeout=self.manager.io_timeout
            )

            base = msg.from_json()
            if 'error' in base or 'consumers' not in base:
                return protocol.from_msg(msg)

            consumers = []
            for item in base['consumers']:
                consumers.append(consumer.ConsumerInfo(**item))

            return consumers

        return await self._run_or_await(fn, on_done)

    async def names(self, stream_name: str, offset: int = 0, on_done: callable = None) -> list[str]:
        """
        Provides a list of consumer names.
        """

        async def fn():
            payload = {'offset': offset}

            msg = await self.manager.request(
                protocol.API.get(protocol.API.CONSUMER_NAMES, stream=stream_name), payload=self._as_json(payload),
                timeout=self.manager.io_timeout
            )

            base = msg.from_json()
            if 'error' in base or 'consumers' not in base:
                return protocol.from_msg(msg)

            streams = []
            for item in base['consumers']:
                streams.append(item)

            return streams

        return await self._run_or_await(fn, on_done)

    async def create(self, cons: consumer.Consumer, push_callback: callable = None,
                     on_done: callable = None) -> consumer.ConsumerCreateResponse:
        """
        Create a consumer, optionally creating a push subscription with it.

        If you don't provide a `push_callback`, you may use the consumer in pull mode by calling `fetch()`. If a
        durable pull consumer already exists, you don't need to call this before using `fetch()`.
        """

        async def fn():
            self.manager.ensure_connected()

            inbox = None
            if push_callback:
                # The difference between a push and a pull consumer is that a push subscriber provides an inbox
                # via the `reply_to` property. If none is provided, you're expected to hit the `next_msg` API.
                inbox = await self.manager.inbox_mgr.get_inbox(push_callback)
                cons.consumer_cfg.deliver_subject = inbox

            if cons.is_durable:
                # Durable consumer includes the consumer name in the URI
                cons.consumer_cfg.durable_name = cons.consumer_cfg.name
                api = protocol.API.get(
                    protocol.API.CONSUMER_CREATE_DURABLE,
                    stream=cons.stream_name,
                    consumer=cons.consumer_cfg.durable_name
                )
            else:
                # Ephemeral consumer still has a name, but not included in the URI
                api = protocol.API.get(protocol.API.CONSUMER_CREATE_EPHEMERAL, stream=cons.stream_name)

            request = consumer.ConsumerInfo(stream_name=cons.stream_name, config=cons.consumer_cfg)
            create_consumer: consumer.ConsumerCreateResponse = protocol.from_msg(
                await self.manager.request(api=api, payload=request.to_json(), timeout=self.manager.io_timeout)
            )

            if not hasattr(create_consumer, "name"):
                self.logger.error(f"Error creating consumer: {create_consumer}")
            else:
                if inbox is not None:
                    self.consumer_map[create_consumer.name] = inbox

            return create_consumer

        return await self._run_or_await(fn, on_done)

    async def delete(self, stream_name: str, consumer_name: str,
                     on_done: callable = None) -> consumer.ConsumerDeleteResponse:
        """
        Deletes a consumer.
        """

        async def fn():
            if consumer_name in self.consumer_map:
                self.manager.inbox_mgr.free_inbox(self.consumer_map[consumer_name], destroy=True)
                del self.consumer_map[consumer_name]

            return protocol.from_msg(await self.manager.request(
                protocol.API.get(protocol.API.CONSUMER_DELETE, stream=stream_name, consumer=consumer_name),
                timeout=self.manager.io_timeout
            ))

        return await self._run_or_await(fn, on_done)
