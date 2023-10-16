from micro_nats.jetstream import protocol
from micro_nats.jetstream.io.manager import SubManager
from micro_nats.jetstream.protocol import stream


class StreamManager(SubManager):
    async def info(self, stream_name: str, on_done: callable = None) -> stream.StreamInfo:
        """
        Returns details on a stream.
        """
        async def fn():
            msg = await self.manager.request(
                protocol.API.get(protocol.API.STREAM_INFO, stream=stream_name), timeout=self.manager.io_timeout
            )
            return protocol.from_msg(msg)

        return await self._run_or_await(fn, on_done)

    async def listing(self, offset: int = 0, on_done: callable = None) -> list[stream.StreamInfo]:
        """
        Provides a list of streams.
        """
        async def fn():
            payload = {'offset': offset}

            msg = await self.manager.request(
                protocol.API.get(protocol.API.STREAM_LIST), payload=self._as_json(payload),
                timeout=self.manager.io_timeout
            )

            base = msg.from_json()
            if 'error' in base or 'streams' not in base:
                return protocol.from_msg(msg)

            streams = []
            for item in base['streams']:
                streams.append(stream.StreamInfo(**item))

            return streams

        return await self._run_or_await(fn, on_done)

    async def names(self, offset: int = 0, on_done: callable = None) -> list[str]:
        """
        Provides a list of stream names.
        """
        async def fn():
            payload = {'offset': offset}

            msg = await self.manager.request(
                protocol.API.get(protocol.API.STREAM_NAMES), payload=self._as_json(payload),
                timeout=self.manager.io_timeout
            )

            base = msg.from_json()
            if 'error' in base or 'streams' not in base:
                return protocol.from_msg(msg)

            streams = []
            for item in base['streams']:
                streams.append(item)

            return streams

        return await self._run_or_await(fn, on_done)

    async def create(self, stream_cfg: stream.StreamConfig, update: bool = False,
                     on_done: callable = None) -> stream.StreamCreateResponse:
        """
        Create or update a stream.
        """
        async def fn():
            self.manager.ensure_connected()

            if not isinstance(stream_cfg.subjects, list):
                stream_cfg.subjects = [stream_cfg.subjects]

            if update:
                api = protocol.API.get(protocol.API.STREAM_UPDATE, stream=stream_cfg.name)
            else:
                api = protocol.API.get(protocol.API.STREAM_CREATE, stream=stream_cfg.name)

            return protocol.from_msg(await self.manager.request(
                api=api, payload=stream_cfg.to_json(), timeout=self.manager.io_timeout
            ))

        return await self._run_or_await(fn, on_done)

    async def delete(self, stream_name: str, on_done: callable = None) -> stream.StreamDeleteResponse:
        """
        Deletes a stream.
        """
        async def fn():
            return protocol.from_msg(await self.manager.request(
                protocol.API.get(protocol.API.STREAM_DELETE, stream=stream_name),
                timeout=self.manager.io_timeout
            ))

        return await self._run_or_await(fn, on_done)

    async def purge(self, stream_name: str, on_done: callable = None) -> stream.StreamPurgeResponse:
        """
        Purges a stream.
        """
        async def fn():
            return protocol.from_msg(await self.manager.request(
                protocol.API.get(protocol.API.STREAM_PURGE, stream=stream_name),
                timeout=self.manager.io_timeout
            ))

        return await self._run_or_await(fn, on_done)
