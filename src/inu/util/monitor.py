import argparse
import asyncio
import logging
import random

from inu import Inu, InuHandler, tz
from inu import error, const
from inu.const import Context
from inu.error import BadRequest
from inu.schema import Alert, Log, Heartbeat
from inu.schema.settings import Settings
from inu.util import Utility
from micro_nats import error as mn_error, model
from micro_nats.jetstream.error import ErrorResponseException
from micro_nats.jetstream.protocol.consumer import Consumer, ConsumerConfig
from micro_nats.util import Time


class Monitor(Utility, InuHandler):
    # Number of logged messages (only counts if there is a limit)
    logged: int = 0

    # Max number of logged messages before exiting
    limit: int = 0

    # Exit request (from limit hit)
    exit: bool = False

    def __init__(self, args: argparse.Namespace):
        super().__init__(args)
        self.logger = logging.getLogger('inu.util.monitor')
        self.inu = Inu(Context(
            device_id=["monitor", f"i{random.randint(1000, 9999)}"],
            nats_server=args.nats,
            has_heartbeat=False,
            settings_class=Settings,
        ), self)

        self.limit = int(self.args.limit or 0)

    async def run(self):
        """
        Main monitor daemon.

        Never returns.
        """
        if not await self.inu.init():
            return

        while not self.exit:
            await asyncio.sleep(0.1)

    async def on_settings_updated(self):
        self.logger.debug("New settings received")

    async def on_connect(self, server: model.ServerInfo):
        self.logger.info("Connected to NATS server")

        stream_tally = 0
        ack_wait = Time.sec_to_nano(1.5)

        start_time = self.args.time
        if start_time:
            try:
                start_time = tz.to_str(start_time)
                self.logger.debug(f"Start time: {start_time}")
            except BadRequest as e:
                self.logger.error(str(e))
                return

        del_pol = ConsumerConfig.DeliverPolicy.BY_START_TIME if start_time else ConsumerConfig.DeliverPolicy.NEW

        try:
            if self.args.heartbeats:
                stream_tally += 1
                await self.inu.js.consumer.create(
                    Consumer(const.Streams.HEARTBEAT, ConsumerConfig(
                        filter_subject=const.Subjects.all(const.Subjects.HEARTBEAT),
                        deliver_policy=del_pol,
                        opt_start_time=start_time,
                        ack_wait=ack_wait,
                    )), self.on_hb,
                )

            if self.args.alerts:
                stream_tally += 1
                await self.inu.js.consumer.create(
                    Consumer(const.Streams.ALERTS, ConsumerConfig(
                        filter_subject=const.Subjects.all(const.Subjects.ALERT),
                        deliver_policy=del_pol,
                        opt_start_time=start_time,
                        ack_wait=ack_wait,
                    )), self.on_alert,
                )

            if self.args.settings:
                stream_tally += 1
                await self.inu.js.consumer.create(
                    Consumer(const.Streams.SETTINGS, ConsumerConfig(
                        filter_subject=const.Subjects.all(const.Subjects.SETTINGS),
                        deliver_policy=del_pol,
                        opt_start_time=start_time,
                        ack_wait=ack_wait,
                    )), self.on_settings,
                )

            if self.args.commands:
                stream_tally += 1
                await self.inu.js.consumer.create(
                    Consumer(const.Streams.COMMAND, ConsumerConfig(
                        filter_subject=const.Subjects.all(const.Subjects.COMMAND),
                        deliver_policy=del_pol,
                        opt_start_time=start_time,
                        ack_wait=ack_wait,
                    )), self.on_command,
                )

            if self.args.logs or stream_tally == 0:
                stream_tally += 1
                await self.inu.js.consumer.create(
                    Consumer(const.Streams.LOGS, ConsumerConfig(
                        filter_subject=const.Subjects.all(const.Subjects.LOG),
                        deliver_policy=del_pol,
                        opt_start_time=start_time,
                        ack_wait=ack_wait,
                    )), self.on_log,
                )

        except mn_error.NotFoundError:
            self.logger.error("Stream not found. Ensure NATS environment is bootstrapped.")
            return

        except ErrorResponseException as e:
            err = e.err_response
            self.logger.error(f"NATS: {err.code}-{err.err_code}: {err.description}")

        except Exception as e:
            self.logger.error(f"Subscribe error: {type(e).__name__}: {e}")
            return

        self.logger.info(f"Monitoring {stream_tally} stream{'s' if stream_tally > 0 else ''}..")

    async def handle_msg(self, msg: model.Message, msg_logic: callable):
        # Raw stream messages (eg last message) can't be ack'd
        if msg.can_ack():
            await self.inu.js.msg.ack(msg)

        if self.limit and self.logged >= self.limit:
            # overflow during shutdown
            return

        try:
            msg_logic()
        except error.Malformed as e:
            self.logger.error(f"Malformed message on subject '{msg.get_subject()}': {str(e)}")
        except Exception as e:
            self.logger.error(f"Error reading subject '{msg.get_subject()}': {str(e)}")

        if self.limit:
            self.logged += 1
            if self.logged >= self.limit:
                self.exit = True

    async def on_log(self, msg: model.Message):
        def handle_log():
            device_id = msg.get_subject()[len(const.Subjects.LOG) + 1:]
            log = Log(msg.get_payload())
            print(f"{msg.time} <{device_id}> [{log.level}] {log.message}")

        await self.handle_msg(msg, handle_log)

    async def on_alert(self, msg: model.Message):
        def handle_alert():
            device_id = msg.get_subject()[len(const.Subjects.ALERT) + 1:]
            alert = Alert(msg.get_payload())
            print(f"{msg.time} <{device_id}> [P{alert.priority}] {alert.message}")

        await self.handle_msg(msg, handle_alert)

    async def on_hb(self, msg: model.Message):
        def handle_hb():
            device_id = msg.get_subject()[len(const.Subjects.HEARTBEAT) + 1:]
            hb = Heartbeat(msg.get_payload())
            print(f"{msg.time} <{device_id}> BEAT ({hb.interval}s)")

        await self.handle_msg(msg, handle_hb)

    async def on_settings(self, msg: model.Message):
        def handle_hb():
            device_id = msg.get_subject()[len(const.Subjects.SETTINGS) + 1:]
            print(f"{msg.time} <{device_id}> NEW SETTINGS :: {msg.get_payload().decode()}")

        await self.handle_msg(msg, handle_hb)

    async def on_command(self, msg: model.Message):
        def handle_hb():
            device_id = msg.get_subject()[len(const.Subjects.COMMAND) + 1:]
            print(f"{msg.time} <{device_id}> CMD :: {msg.get_payload().decode()}")

        await self.handle_msg(msg, handle_hb)
