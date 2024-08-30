import argparse
import asyncio
import json
import logging
import os.path
import random

from inu import Inu, InuHandler
from inu import const
from micro_nats import error as mn_error, model
from micro_nats.jetstream.error import ErrorResponseException
from micro_nats.jetstream.protocol.consumer import Consumer, ConsumerConfig
from micro_nats.util import Time
from overwatch.const import AlarmState
from overwatch.tts import Tts


class Overwatch(InuHandler):
    def __init__(self, args: argparse.Namespace):
        self.logger = logging.getLogger('inu.overwatch')
        self.config = {}

        self.voice = None
        self.engine = None
        self.alarm_id = None

        self.state = AlarmState.DISARMED

        self.load_config(args.config)
        self.tts = Tts(self.voice, self.engine)

        self.inu = Inu(const.Context(
            device_id=["overwatch", f"i{random.randint(1000, 9999)}"],
            nats_server=self.get_config("nats", "nats://127.0.0.1:4222"),
        ), self)

        self.consumers = [
            (const.Streams.COMMAND, const.Subjects.COMMAND, self.on_command),
        ]

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
        self.alarm_id = self.get_config("alarm_id", "general")

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
        except asyncio.exceptions.CancelledError:
            pass

    async def on_connect(self, server: model.ServerInfo):
        self.logger.info("Connected to NATS server")
        ack_wait = Time.sec_to_nano(1.5)

        try:
            for stream_name, subj, cb in self.consumers:
                self.logger.debug(f"Subscribing to '{stream_name}'")
                await self.inu.js.consumer.create(
                    Consumer(stream_name, ConsumerConfig(
                        filter_subject=const.Subjects.all(subj),
                        deliver_policy=ConsumerConfig.DeliverPolicy.NEW,
                        ack_wait=ack_wait,
                    )), cb,
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

    async def on_command(self, msg: model.Message):
        """
        Command (eg trigger). Send to logging tool.
        """
        await self.inu.js.msg.ack(msg)
        subj = msg.get_subject()[len(const.Subjects.COMMAND) + 1:].split(".", 1)
        cmd = subj[0]
        device_id = subj[1]

        if cmd != "alarm":
            return
