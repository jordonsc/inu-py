import argparse
import logging
import random

from micro_nats.error import NotFoundError
from micro_nats.jetstream.error import ErrorResponseException
from micro_nats.jetstream.protocol.stream import StreamConfig
from micro_nats.util import Time
from .. import Inu, InuHandler, const
from ..util import Utility


class Bootstrap(Utility, InuHandler):
    def __init__(self, args: argparse.Namespace):
        super().__init__(args)
        self.logger = logging.getLogger('inu.util.bootstrap')
        self.inu = Inu(const.Context(
            device_id=["bootstrap", f"i{random.randint(1000, 9999)}"],
            nats_server=args.nats,
        ), self)

    async def run(self):
        """
        Execute the bootstrap process.
        """
        if not await self.inu.init():
            return

        try:
            if self.args.clean or self.args.delete:
                # Delete any existing streams
                await self.delete_streams()

            if not self.args.delete:
                # Configure all Inu streams
                await self.configure_streams()

            # All done
            await self.inu.log(f"Bootstrap completed ({self.inu.device_id})")

        except ErrorResponseException as e:
            err = e.err_response
            self.logger.error(f"NATS: {err.code}-{err.err_code}: {err.description}")

        except Exception as e:
            self.logger.error(f"Aborting due to errors: {type(e).__name__}: {str(e)}")

    async def delete_streams(self):
        """
        Delete any existing Inu streams.
        """
        self.logger.info("Cleaning streams")

        async def clean(s: str):
            try:
                await self.inu.js.stream.delete(s)
                self.logger.warning(f"stream '{s}' deleted")
            except NotFoundError:
                pass

        await clean(const.Streams.LOGS)
        await clean(const.Streams.ALERTS)
        await clean(const.Streams.STATUS)
        await clean(const.Streams.COMMAND)
        await clean(const.Streams.HEARTBEAT)
        await clean(const.Streams.SETTINGS)

    async def configure_streams(self):
        """
        Created all required Inu NATS streams.
        """
        self.logger.info("Preparing streams")
        # Log stream
        await self.inu.js.stream.create(StreamConfig(
            name=const.Streams.LOGS,
            description="Inu network logs",
            subjects=[const.Subjects.all(const.Subjects.LOG)],
            max_msgs_per_subject=100000,
            retention=StreamConfig.RetentionPolicy.LIMITS,
            storage=StreamConfig.StorageType.FILE,
            discard=StreamConfig.DiscardPolicy.OLD
        ))

        # Alerts stream
        await self.inu.js.stream.create(StreamConfig(
            name=const.Streams.ALERTS,
            description="Inu network alerts",
            subjects=[const.Subjects.all(const.Subjects.ALERT)],
            max_msgs_per_subject=100000,
            retention=StreamConfig.RetentionPolicy.LIMITS,
            storage=StreamConfig.StorageType.FILE,
            discard=StreamConfig.DiscardPolicy.OLD
        ))

        # Status stream
        await self.inu.js.stream.create(StreamConfig(
            name=const.Streams.STATUS,
            description="Inu network device statuses",
            subjects=[const.Subjects.all(const.Subjects.STATUS)],
            max_msgs_per_subject=1000,
            retention=StreamConfig.RetentionPolicy.LIMITS,
            storage=StreamConfig.StorageType.FILE,
            discard=StreamConfig.DiscardPolicy.OLD
        ))

        # Command stream
        await self.inu.js.stream.create(StreamConfig(
            name=const.Streams.COMMAND,
            description="Inu network device commands",
            subjects=[const.Subjects.all(const.Subjects.COMMAND)],
            max_msgs_per_subject=1000,
            retention=StreamConfig.RetentionPolicy.LIMITS,
            storage=StreamConfig.StorageType.FILE,
            discard=StreamConfig.DiscardPolicy.OLD
        ))

        # Heartbeat stream
        await self.inu.js.stream.create(StreamConfig(
            name=const.Streams.HEARTBEAT,
            description="Inu network device heartbeats",
            subjects=[const.Subjects.all(const.Subjects.HEARTBEAT)],
            max_msgs_per_subject=3,
            max_age=Time.sec_to_nano(3 * 24 * 3600),  # 3 days - purge temp clients
            retention=StreamConfig.RetentionPolicy.LIMITS,
            storage=StreamConfig.StorageType.FILE,
            discard=StreamConfig.DiscardPolicy.OLD
        ))

        # Settings stream
        await self.inu.js.stream.create(StreamConfig(
            name=const.Streams.SETTINGS,
            description="Inu network device settings",
            subjects=[const.Subjects.all(const.Subjects.SETTINGS)],
            max_msgs_per_subject=100,
            retention=StreamConfig.RetentionPolicy.LIMITS,
            storage=StreamConfig.StorageType.FILE,
            discard=StreamConfig.DiscardPolicy.OLD
        ))
