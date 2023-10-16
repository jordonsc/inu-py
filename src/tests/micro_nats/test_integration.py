import asyncio
import unittest

from micro_nats import model, io, error
from micro_nats.client import Client as Nats
from micro_nats.jetstream.client import Client as Jetstream
from micro_nats.jetstream.protocol import stream, consumer
from micro_nats.util import Time
from micro_nats.util.asynchronous import TaskPool


class TestClientCommands(unittest.IsolatedAsyncioTestCase, io.IoHandler):
    CMD_DELAY = 0.05

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.nats = Nats(model.ServerContext("nats://127.0.0.1:4222"), handler=self)
        self.js = Jetstream(self.nats)
        self.pool = TaskPool()

        self.test_stream = stream.StreamConfig(
            name="mnats_test",
            description="MicroNats test stream",
            subjects="mnats.test.>",  # NB: this will be turned into a list for the create request
            max_consumers=3,
        )

        self.test_consumer = consumer.Consumer(
            stream_name="mnats_test",
            is_durable=False,
            consumer_cfg=consumer.ConsumerConfig(
                name="mnats_test_consumer",
                description="MicroNats test consumer",
                filter_subject="mnats.test.>",
                deliver_policy=consumer.ConsumerConfig.DeliverPolicy.LAST,
                # opt_start_time="2023-10-04T00:00:00Z",
                ack_wait=Time.sec_to_nano(3),
            )
        )

    async def test_base_flow(self):
        try:
            # Async - will connect and do a handshake
            await self.nats.connect()
        except error.ConnectionRefused:
            self.assertTrue(False, "Integration tests require a live connection to a NATS server with JS support")
            return

        # You could also use the `on_connect()` callback, which makes a good place to start consumers
        # For the sake of a linear flow in tests, we'll just poll
        while not self.nats.is_connected():
            await asyncio.sleep(0.01)

        self.assertTrue(self.nats.jetstream_supported())

        # Delete lingering data from previous runs
        try:
            await self.js.stream.delete("mnats_test")
        except error.NotFoundError:
            pass

        # Create stream
        s = await self.js.stream.create(self.test_stream)
        self.assertEqual(s.config.retention, stream.StreamConfig.RetentionPolicy.LIMITS)
        self.assertEqual(s.config.max_age, 0)
        await asyncio.sleep(self.CMD_DELAY)

        # Update stream
        self.test_stream.max_age = Time.sec_to_nano(3600)
        s = await self.js.stream.create(self.test_stream, update=True)
        self.assertEqual(s.config.max_age, Time.sec_to_nano(3600))
        await asyncio.sleep(self.CMD_DELAY)

        # Stream info
        info = await self.js.stream.info("mnats_test")
        self.assertEqual(info.config.description, "MicroNats test stream")

        # Publish some messages to the stream
        await self.nats.publish("mnats.test.foo", "hello")
        await self.nats.publish("mnats.test.foo", "world")
        await asyncio.sleep(self.CMD_DELAY)

        # Stream get message
        msg = await self.js.msg.get_last("mnats_test", "mnats.test.*")
        self.assertEqual(msg.stream_seq, 2)
        self.assertEqual(msg.get_payload(), b'world')
        msg = await self.js.msg.get_seq("mnats_test", 1)
        self.assertEqual(msg.stream_seq, 1)
        self.assertEqual(msg.get_payload(), b'hello')

        # Stream del message
        r = await self.js.msg.delete("mnats_test", 2)
        self.assertTrue(r.success)
        await asyncio.sleep(self.CMD_DELAY)

        msg = await self.js.msg.get_last("mnats_test", "mnats.test.*")
        self.assertEqual(msg.stream_seq, 1)
        self.assertEqual(msg.get_payload(), b'hello')

        # Confirm seq 2 deleted
        with self.assertRaises(error.NotFoundError):
            await self.js.msg.get_seq("mnats_test", 2)

        # Stream purge
        r = await self.js.stream.purge("mnats_test")
        self.assertTrue(r.success)
        self.assertTrue(r.purged, 1)

        # Stream names
        streams = await self.js.stream.names()
        self.assertGreaterEqual(len(streams), 1)
        self.assertTrue("mnats_test" in streams)

        # Stream list
        streams = await self.js.stream.listing()
        self.assertGreaterEqual(len(streams), 1)
        self.assertIsNotNone(streams[0].config.name)

        # Consumer create
        cons = await self.js.consumer.create(self.test_consumer)
        self.assertEqual(cons.name, self.test_consumer.consumer_cfg.name)
        self.assertEqual(cons.stream_name, "mnats_test")
        self.assertFalse(cons.push_bound)
        await asyncio.sleep(self.CMD_DELAY)

        # Consumer list
        consumers = await self.js.consumer.listing("mnats_test")
        self.assertEqual(len(consumers), 1)
        self.assertEqual(consumers[0].name, "mnats_test_consumer")

        # Consumer names
        consumers = await self.js.consumer.names("mnats_test")
        self.assertEqual(len(consumers), 1)
        self.assertTrue("mnats_test_consumer" in consumers)

        # Consumer info
        info = await self.js.consumer.info("mnats_test", "mnats_test_consumer")
        self.assertEqual(info.name, "mnats_test_consumer")
        self.assertFalse(info.push_bound)

        # Consumer delete
        r = await self.js.consumer.delete("mnats_test", "mnats_test_consumer")
        self.assertTrue(r.success)

        # Stream delete
        r = await self.js.stream.delete("mnats_test")
        self.assertTrue(r.success)

        await asyncio.sleep(self.CMD_DELAY)

        # Confirm deleted
        with self.assertRaises(error.NotFoundError):
            await self.js.consumer.info("mnats_test", "mnats_test_consumer")

        with self.assertRaises(error.NotFoundError):
            await self.js.stream.info("mnats_test")
