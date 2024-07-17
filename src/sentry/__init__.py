import argparse
import asyncio
import json
import logging
import os.path
import random
import time

from inu import Inu, InuHandler, Status
from inu import const
from inu.const import Priority
from inu.schema import Alert, Log, Heartbeat
from micro_nats import error as mn_error, model
from micro_nats.jetstream.error import ErrorResponseException
from micro_nats.jetstream.protocol.consumer import Consumer, ConsumerConfig
from micro_nats.util import Time
from sentry import logger as sentry_logger, alerter as sentry_alerter


class Device:
    def __init__(self, device_id: str, hb_freq: int):
        self.device_id = device_id
        self.heartbeat_freq = hb_freq
        self.last_heartbeat = time.monotonic()

    def has_expired(self, missed=5) -> bool:
        """
        Check if the device is considered offline (heartbeat expired).
        """
        if self.last_heartbeat is None:
            return False

        return (time.monotonic() - self.last_heartbeat) > (self.heartbeat_freq * missed)

    def beat(self):
        """
        Received a heartbeat from this device.
        """
        self.last_heartbeat = time.monotonic()


class Sentry(InuHandler):
    MISSED_HEARTBEATS_ALARM = 10
    DEFAULT_PRIORITY = 3

    def __init__(self, args: argparse.Namespace):
        self.sentry_logger: sentry_logger.Logger | None = None
        self.sentry_alerter: sentry_alerter.Alerter | None = None
        self.config = {}

        self.logger = logging.getLogger('inu.sentry')
        self.load_config(args.config)

        self.inu = Inu(const.Context(
            device_id=["sentry", f"i{random.randint(1000, 9999)}"],
            nats_server=self.get_config("nats", "nats://127.0.0.1:4222"),
        ), self)

        self.device_pool = {}
        self.consumers = [
            (const.Streams.HEARTBEAT, const.Subjects.HEARTBEAT, self.on_hb),
            (const.Streams.ALERTS, const.Subjects.ALERT, self.on_alert),
            (const.Streams.SETTINGS, const.Subjects.SETTINGS, self.on_settings),
            (const.Streams.COMMAND, const.Subjects.COMMAND, self.on_command),
            (const.Streams.LOGS, const.Subjects.LOG, self.on_log),
            (const.Streams.STATUS, const.Subjects.STATUS, self.on_status),
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
        log_engine = self.get_config(["logger", "engine"])
        if log_engine == "loki":
            self.sentry_logger = sentry_logger.LokiLogger(self.get_config("logger"))
        else:
            self.logger.warning("No known logger configured")

        # Create an alert engine from config
        alert_engine = self.get_config(["alerter", "engine"])
        if alert_engine == "pagerduty":
            self.sentry_alerter = sentry_alerter.PagerDuty(self.get_config("alerter"))
        else:
            self.logger.warning("No known alerter configured")

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

        try:
            while True:
                await self.check_heartbeats()
                await asyncio.sleep(0.1)
        except asyncio.exceptions.CancelledError:
            pass

    async def check_heartbeats(self):
        """
        Iterates each known device and checks if their heartbeat has expired.

        If it has, it will raise an alert and remove the device from the pool.
        """
        del_list = []
        for device_id, device in self.device_pool.items():
            if device.has_expired(self.MISSED_HEARTBEATS_ALARM):
                alert = f"Device <{device_id}> died"
                await self.inu.alert(alert, await self.get_device_priority(device_id))
                del_list.append(device_id)

        for device_id in del_list:
            del self.device_pool[device_id]

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

    async def publish_log(self, stream: str, ts: int, msg: str, labels: dict):
        """
        Send a log directly to the logging engine.
        """
        if self.sentry_logger is None:
            return

        await self.sentry_logger.publish(stream=stream, ts=ts, msg=msg, labels=labels)

    async def on_log(self, msg: model.Message):
        """
        Generic log line - send to the logging system (eg Loki).
        """
        await self.inu.js.msg.ack(msg)
        device_id = msg.get_subject()[len(const.Subjects.LOG) + 1:]
        log = Log(msg.get_payload())
        await self.publish_log(
            const.Streams.LOGS,
            msg.time_ns,
            json.dumps({
                "device_id": device_id,
                "log_level": log.level,
                "message": log.message,
            }),
            {
                "device_id": device_id,
                "log_level": log.level,
            }
        )

    async def on_alert(self, msg: model.Message):
        """
        Alert - this needs to go to paging tool (eg Pagerduty) and log engine.
        """
        await self.inu.js.msg.ack(msg)
        device_id = msg.get_subject()[len(const.Subjects.ALERT) + 1:]
        alert = Alert(msg.get_payload())

        # Send to logger
        await self.publish_log(
            const.Streams.ALERTS,
            msg.time_ns,
            json.dumps({
                "device_id": device_id,
                "priority": f"P{alert.priority}",
                "message": alert.message,
            }),
            {
                "device_id": device_id,
                "priority": str(alert.priority),
            }
        )

        # Send to alerter
        if self.sentry_alerter is not None and alert.priority < Priority.LOWEST:
            await self.sentry_alerter.publish(device_id, alert.message, alert.priority)

    async def get_device_priority(self, device_id: str) -> int:
        """
        Looks up a device to determine its device priority. Will use a default if settings now found or missing.
        """
        try:
            dvc_settings = await self.inu.js.msg.get_last(
                const.Streams.SETTINGS,
                const.Subjects.fqs(const.Subjects.SETTINGS, device_id)
            )

            p = int(dvc_settings.from_json()['device_priority'])
            return min(const.Priority.LOWEST, max(const.Priority.HIGHEST, p))
        except mn_error.NotFoundError:
            return self.DEFAULT_PRIORITY
        except Exception as e:
            self.logger.error(f"Error getting device priority - {type(e)}: {e}")
            return self.DEFAULT_PRIORITY

    async def on_hb(self, msg: model.Message):
        """
        Heartbeat from a device. Used to track when a device goes offline.
        """
        await self.inu.js.msg.ack(msg)
        device_id = msg.get_subject()[len(const.Subjects.HEARTBEAT) + 1:]
        hb = Heartbeat(msg.get_payload())

        if device_id in self.device_pool:
            self.device_pool[device_id].beat()
        else:
            dvc = Device(device_id, hb_freq=hb.interval)
            self.device_pool[device_id] = dvc
            await self.inu.log(f"Device <{device_id}> now online")

    async def on_settings(self, msg: model.Message):
        """
        New settings have been published. Send to logging tool.
        """
        device_id = msg.get_subject()[len(const.Subjects.SETTINGS) + 1:]
        await self.publish_log(
            const.Streams.SETTINGS,
            msg.time_ns,
            json.dumps({
                "device_id": device_id,
                "settings": msg.from_json(),
            }),
            {
                "device_id": device_id,
            }
        )

    async def on_command(self, msg: model.Message):
        """
        Command (eg trigger). Send to logging tool.
        """
        await self.inu.js.msg.ack(msg)
        subj = msg.get_subject()[len(const.Subjects.COMMAND) + 1:].split(".", 1)
        cmd = subj[0]
        device_id = subj[1]
        await self.publish_log(
            const.Streams.COMMAND,
            msg.time_ns,
            json.dumps({
                "device_id": device_id,
                "command": cmd,
                "payload": msg.from_json(),
            }),
            {
                "device_id": device_id,
                "command": cmd,
            }
        )

    async def on_status(self, msg: model.Message):
        """
        Device change state.
        """
        await self.inu.js.msg.ack(msg)
        device_id = msg.get_subject()[len(const.Subjects.STATUS) + 1:]
        status = Status(msg.get_payload())
        await self.publish_log(
            const.Streams.STATUS,
            msg.time_ns,
            json.dumps({
                "device_id": device_id,
                "enabled": status.enabled,
                "locked": status.locked,
                "active": status.active,
                "status": status.status,
            }),
            {
                "device_id": device_id,
                "status_enabled": str(status.enabled),
                "status_locked": str(status.locked),
                "status_active": str(status.active),
            }
        )
