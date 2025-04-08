import argparse
import asyncio
import json
import logging
import os.path
import random

from inu import Inu, InuHandler, const as inu_const
from inu.schema import Alarm, Announcement
from micro_nats import error as mn_error, model
from micro_nats.jetstream.error import ErrorResponseException
from micro_nats.jetstream.protocol.consumer import Consumer, ConsumerConfig
from micro_nats.util import Time
from overwatch.audio import AudioController


class Overwatch(InuHandler):
    def __init__(self, args: argparse.Namespace):
        self.logger = logging.getLogger('inu.overwatch')
        self.config = {}

        # Default settings
        self.voice = None
        self.engine = None
        self.sample_rate = None
        self.alarm_default = None
        self.announcement_default = None
        self.audio_base_path = None
        self.alarm_preplay = 0

        # Alarm active/stand-down state
        self.alarm_state = False
        self.alarm_fn = None

        # Bring in the JSON config
        self.load_config(args.config)

        # Audio engine for TTS & alarms
        self.audio = AudioController(self.voice, self.engine)

        # Inu service for network comms
        self.inu = Inu(inu_const.Context(
            device_id=["overwatch", f"i{random.randint(1000, 9999)}"],
            nats_server=self.get_config("nats", "nats://127.0.0.1:4222"),
        ), self)

        self.logger.info(f"Overwatch initialised with voice={self.voice}, engine={self.engine}; audio_path={self.audio_base_path}")

        
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
        self.sample_rate = self.get_config("sample_rate", "22050")
        self.alarm_default = self.get_config("alarm_default", "klaxon-1")
        self.announcement_default = self.get_config("announcement_default", "announcement-1")
        self.audio_base_path = self.get_config("audio_path", "/etc/overwatch/audio")
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

        await self.audio.enqueue_tts("Overwatch online")

        try:
            while True:
                await asyncio.sleep(0.1)
                await self.audio.process_queue()

                if self.alarm_state and not self.audio.has_content():
                    await self.audio.enqueue_from_file(self.alarm_fn)

        except asyncio.exceptions.CancelledError:
            pass

    async def on_connect(self, _: model.ServerInfo):
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

            self.logger.info(f"Subscribing to announcements stream..")
            await self.inu.js.consumer.create(
                Consumer(inu_const.Streams.COMMAND, ConsumerConfig(
                    filter_subject=inu_const.Subjects.fqs(inu_const.Subjects.COMMAND, inu_const.Subjects.COMMAND_ANNOUNCE),
                    deliver_policy=ConsumerConfig.DeliverPolicy.NEW,
                    ack_wait=ack_wait,
                )), self.on_announce,
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
        try:
            alarm = Alarm(msg.get_payload())
            self.logger.info(f"Alarm command received: {alarm}; stream_seq={msg.stream_seq}, consumer_seq={msg.consumer_seq}")
        except:
            self.logger.error(f"Alarm decode error: {msg.get_payload()}")
            if msg.can_ack():
                await self.inu.js.msg.term(msg)
            return

        if msg.can_ack():
            await self.inu.js.msg.ack(msg)

        if alarm.active:
            # Trigger alarm
            self.alarm_state = True

            # Alarm track is optional, either use the default or the specified track
            if alarm.track is not None:
                self.alarm_fn = os.path.join(self.audio_base_path, f"{alarm.track}.mp3")
            else:
                self.alarm_fn = os.path.join(self.audio_base_path, f"{self.alarm_default}.mp3")

            # Pre-play alarm sound before speaking the 'cause'
            if self.alarm_preplay > 0:
                for _ in range(self.alarm_preplay):
                    await self.audio.enqueue_from_file(self.alarm_fn)

            if alarm.cause:
                await self.audio.enqueue_tts(alarm.cause)

        else:
            # Stand down alarm
            self.alarm_state = False
            self.alarm_fn = None

    async def on_announce(self, msg: model.Message):
        """
        Announcement command received.
        """
        try:
            annnouncement = Announcement(msg.get_payload())
            self.logger.info(f"Announcement received: {annnouncement}; stream_seq={msg.stream_seq}, consumer_seq={msg.consumer_seq}")
        except:
            self.logger.error(f"Announcement decode error: {msg.get_payload()}")
            if msg.can_ack():
                await self.inu.js.msg.term(msg)
            return

        if msg.can_ack():
            await self.inu.js.msg.ack(msg)
        
        # Optionally have an announcement chime before the message
        if annnouncement.chime:
            audio_track = annnouncement.track if annnouncement.track is not None else self.announcement_default
            audio_fn = os.path.join(self.audio_base_path, f"{audio_track}.mp3")
            await self.audio.enqueue_from_file(audio_fn)

        await self.audio.enqueue_tts(annnouncement.message)
