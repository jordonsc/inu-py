import argparse
import asyncio
import json
import logging
import os.path
import random

from inu import Inu, InuHandler, const as inu_const
from inu.schema import Alarm
from micro_nats import error as mn_error, model
from micro_nats.jetstream.error import ErrorResponseException
from micro_nats.jetstream.protocol.consumer import Consumer, ConsumerConfig
from micro_nats.util import Time
from overwatch.tts import Tts


class Overwatch(InuHandler):
    def __init__(self, args: argparse.Namespace):
        self.logger = logging.getLogger('inu.overwatch')
        self.config = {}

        self.voice = None
        self.engine = None

        self.alarm_state = False
        self.alarm_fn = None
        self.alarm_preplay = 0

        self.load_config(args.config)
        self.tts = Tts(self.voice, self.engine)

        self.inu = Inu(inu_const.Context(
            device_id=["overwatch", f"i{random.randint(1000, 9999)}"],
            nats_server=self.get_config("nats", "nats://127.0.0.1:4222"),
        ), self)

        self.logger.info(f"Overwatch initialised with voice={self.voice}, engine={self.engine}; alarm={self.alarm_fn}")

        
    def load_config(self, fn):
        """
        Load the settings.json file. Should only ever be called once.
        """
        if not os.path.exists(fn):
            raise FileNotFoundError(f"Config file not found at: {fn}")

        with open(fn) as fp:
            self.config = json.load(fp)

        # Create a log engine from config
        self.voice = self.get_config("voice", "Amy")
        self.engine = self.get_config("engine", "neural")
        self.alarm_fn = self.get_config("alarm_file", None)
        self.alarm_preplay = self.get_config("alarm_preplay", 0)

    def get_config(self, key: str | list, default=None):
        """
        Get a setting from the local config, or return the default.
        """
        if isinstance(key, list):
            path = self.config
            for subkey in key:
                if subkey not in path:
                    return default
                path = path[subkey]
            return path

        if key in self.config:
            return self.config[key]
        else:
            return default

    async def run(self):
        # Init Inu
        if not await self.inu.init():
            return

        await self.tts.play("Overwatch online")

        try:
            while True:
                await asyncio.sleep(0.1)

                if self.alarm_state and not self.tts.playing and self.alarm_fn is not None:
                        await self.tts.play_from_file(self.alarm_fn, wait=True)

        except asyncio.exceptions.CancelledError:
            pass

    async def on_connect(self, server: model.ServerInfo):
        self.logger.info("Connected to NATS server")
        ack_wait = Time.sec_to_nano(10)

        try:
            self.logger.info(f"Subscribing to alarm stream..")
            await self.inu.js.consumer.create(
                Consumer(inu_const.Streams.COMMAND, ConsumerConfig(
                    filter_subject=inu_const.Subjects.fqs(inu_const.Subjects.COMMAND, inu_const.Subjects.COMMAND_ALARM),
                    deliver_policy=ConsumerConfig.DeliverPolicy.NEW,
                    ack_wait=ack_wait,
                )), self.on_alarm,
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

    async def on_alarm(self, msg: model.Message):
        """
        Alarm command received.
        """
        if msg.can_ack():
            await self.inu.js.msg.in_progress(msg)

        alarm = Alarm(msg.get_payload())
        self.logger.info(f"Alarm command received: {alarm}; stream_seq={msg.stream_seq}, consumer_seq={msg.consumer_seq}")

        if msg.can_ack():
            await self.inu.js.msg.ack(msg)

        if alarm.active:
            # Trigger alarm
            self.alarm_state = True

            # Pre-play alarm sound before speaking the cause
            if self.alarm_preplay > 0:
                for _ in range(self.alarm_preplay):
                    # Check we weren't stood down during pre-play
                    if self.alarm_state:
                        await self.tts.play_from_file(self.alarm_fn, wait=True)                    

            if self.alarm_state:
                # Only play the cause if the alarm is still active (might have been disabled during pre-play)
                if alarm.cause:
                    await self.tts.play(alarm.cause)
                else:
                    await self.tts.play("Security breach detected")
        else:
            # Stand down alarm
            self.alarm_state = False
            await self.tts.play("Alarm standing down")

