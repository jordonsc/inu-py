import asyncio
import json
import logging
import time

from micro_nats import io, model
from micro_nats.client import Client as NatsClient
from micro_nats.jetstream.client import Client as JsClient
from micro_nats.jetstream.error import ErrorResponseException
from micro_nats.jetstream.protocol import consumer
from micro_nats.util import Time
from micro_nats.util.asynchronous import TaskPool

from . import error, const, schema
from .schema import Heartbeat
from .schema.settings import Settings
from .schema.status import Status


class InuHandler:
    async def on_settings_updated(self):
        pass

    async def on_connect(self, server: model.ServerInfo):
        pass

    async def on_disconnect(self):
        pass


class Inu(io.IoHandler):
    def __init__(self, context: const.Context, handler: InuHandler | None = None):
        self.logger = logging.getLogger('inu')
        self.context = context
        self.settings = Settings()
        self.handler = handler
        self.pool = TaskPool()
        self.has_settings = False
        self.hb_task = None
        self.state = Status(enabled=False, locked=False, active=False, status="")

        # Update this with LAN address for heartbeats
        self.local_address = ""

        if isinstance(self.context.device_id, list):
            self.device_id = ".".join(self.context.device_id)
        else:
            self.device_id = self.context.device_id

        self.app_name = self.device_id.split(".")[0]

        if self.context.settings_class is not None and not issubclass(self.context.settings_class, Settings):
            raise error.BadRequest("Settings class is not a subclass of `Settings`")

        self.nats = NatsClient(model.ServerContext(self.context.nats_server), self)
        self.js = JsClient(self.nats)

    async def init(self) -> bool:
        """
        Brings an application online.

        Establishes a NATS connections, (if applicable) will acquire app settings, begins heartbeat, etc.

        Returns False if it could not get a NATS connection.
        """
        try:
            if not self.nats.is_connected():
                self.logger.debug("Init: NATS..")
                await self.nats.connect()
                await self._wait_for_nats_connect()

            return True

        except error.NoConnection:
            self.logger.error("No connection to NATS server, aborting")
            return False

        except Exception as e:
            self.logger.error(f"Init error: {type(e).__name__}: {e}")
            return False

    async def _wait_for_nats_connect(self):
        start_time = time.time()
        while not self.nats.is_connected():
            if time.time() - start_time > self.context.io_timeout:
                raise error.NoConnection("Timeout connecting to NATS server")

            await asyncio.sleep(0.01)

    async def init_settings(self):
        """
        Subscribes to the settings stream on the subject of this device id.

        `on_settings_updated()` will be called on the provided `NatsHandler` when new messages arrive.
        """
        assert self.context.settings_class is not None, "Settings class is not defined"

        try:
            self.logger.debug(f"Subscribing to settings against schema {self.context.settings_class.__name__}")
            await self.js.consumer.create(
                consumer.Consumer(
                    const.Streams.SETTINGS,
                    consumer_cfg=consumer.ConsumerConfig(
                        filter_subject=const.Subjects.fqs(const.Subjects.SETTINGS, self.device_id),
                        deliver_policy=consumer.ConsumerConfig.DeliverPolicy.LAST,
                        ack_wait=Time.sec_to_nano(5),
                    )
                ), push_callback=self._on_settings,
            )

        except ErrorResponseException as e:
            err = e.err_response
            self.logger.error(f"Error subscribing to device settings: {err.code}-{err.err_code}: {err.description}")

        except Exception as e:
            self.logger.error(f"Error subscribing to device settings: {type(e).__name__}: {e}")

    async def _on_settings(self, msg: model.Message):
        try:
            self.settings = self.context.settings_class(msg.get_payload())
            if self.has_settings:
                await self.log("Applied new settings")
            self.has_settings = True
            await self.js.msg.ack(msg)
        except Exception as e:
            await self.js.msg.nack(msg)
            await self.log(f"Error applying new settings: {type(e).__name__}: {e}")
            self.logger.error(f"Error updating device settings: {type(e).__name__}: {e}")

        if self.handler:
            self.pool.run(self.handler.on_settings_updated())

    async def init_heartbeat(self):
        """
        Creates a background worker that dispatches heartbeat messages at the configured interval.

        If the heartbeat interval changes (in the settings object), this worker will respond in kind.
        """
        if not self.settings.heartbeat_interval:
            self.settings.heartbeat_interval = 5

        self.logger.debug(f"Beginning heartbeat, interval {self.settings.heartbeat_interval}")
        self.hb_task = asyncio.create_task(self._run_heartbeat())

    async def _run_heartbeat(self):
        last_beat = 0

        try:
            while True:
                if not isinstance(self.settings, Settings) or not self.settings.heartbeat_interval:
                    interval = 5
                else:
                    interval = int(self.settings.heartbeat_interval)

                if time.time() - last_beat >= interval:
                    hb = Heartbeat(interval=interval, build=const.INU_BUILD, local_addr=self.local_address)

                    try:
                        self.logger.debug("beat")
                        await self.nats.publish(
                            const.Subjects.fqs(const.Subjects.HEARTBEAT, self.device_id), hb.marshal()
                        )
                    except Exception as e:
                        self.logger.error(f"Heartbeat error: {type(e).__name__}: {str(e)}")

                    last_beat = time.time()

                await asyncio.sleep(1)

        except asyncio.CancelledError:
            self.logger.debug(f"Heartbeat dying")

    async def _kill_heartbeat(self):
        if self.hb_task:
            self.hb_task.cancel()
            self.hb_task = None

    async def command(self, sub_cmd: str, data: dict = None):
        """
        Dispatch a command + sub-command message.
        """
        if data is None:
            data = {}

        try:
            await self.nats.publish(
                const.Subjects.fqs([const.Subjects.COMMAND, sub_cmd], self.device_id),
                json.dumps(data)
            )
        except Exception as e:
            self.logger.error(f"Command error: {type(e).__name__}: {str(e)}")

    async def status(self, active: bool = None, status: str = None, enabled: bool = None, locked: bool = None):
        """
        Update and publish the current device state.
        """
        if active is not None:
            self.state.active = active
        if status is not None:
            self.state.status = status
        if enabled is not None:
            self.state.enabled = enabled
        if locked is not None:
            self.state.locked = locked

        self.logger.debug(f"Device state: {self.state}")

        try:
            await self.nats.publish(
                const.Subjects.fqs(const.Subjects.STATUS, self.device_id),
                json.dumps(self.state.marshal())
            )
        except Exception as e:
            self.logger.error(f"Status error: {type(e).__name__}: {str(e)}")

    async def activate(self, status_msg: str = ""):
        """
        Sets state to active to True & sets the status string, then dispatches a `status` message.
        """
        await self.status(active=True, status=status_msg)

    async def deactivate(self, status_msg: str = ""):
        """
        Sets state active to False & clears the status string, then dispatches a `status` message.
        """
        await self.status(active=False, status=status_msg)

    async def log(self, message: str, level: str = const.LogLevel.INFO):
        """
        Dispatch a log message on the device's log subject.
        """
        await self.log_s(schema.Log(message=message, level=level))

    async def log_s(self, log: schema.Log):
        """
        Schema-form of `log()`
        """
        self.logger.info(f"LOG [{log.level.upper()}]: {log.message}")
        try:
            await self.nats.publish(const.Subjects.fqs(const.Subjects.LOG, self.device_id), log.marshal())
        except Exception as e:
            self.logger.error(f"Log error: {type(e).__name__}: {str(e)}")

    async def alert(self, message: str, priority: int = const.Priority.P3):
        """
        Create an alert, designed for human intervention.

        Typically, this will trigger an alarm - a pager for example - that will get immediate attention. Priority P1 &
        P2 are for urgent alerts (read: will wake user) and P3 & P4 for less urgent (read: will not wake).
        """
        await self.alert_s(schema.Alert(message=message, priority=priority))

    async def alert_s(self, alert: schema.Alert):
        """
        Schema-form of `alert()`.
        """
        self.logger.info(f"ALERT [P{alert.priority}]: {alert.message}")
        try:
            await self.nats.publish(const.Subjects.fqs(const.Subjects.ALERT, self.device_id), alert.marshal())
        except Exception as e:
            self.logger.error(f"Failed to publish alert: {type(e).__name__}: {str(e)}")

    async def on_connect(self, server: model.ServerInfo):
        if self.context.settings_class is not None:
            self.logger.debug("Init: settings..")
            await self.init_settings()

        if self.context.has_heartbeat:
            self.logger.debug("Init: heartbeat..")
            await self.init_heartbeat()

        self.logger.info(f"Connected to NATS server: {server}")
        self.pool.run(self.handler.on_connect(server))

    async def on_disconnect(self):
        await self.js.flush_inbox()
        await self._kill_heartbeat()
        self.has_settings = False
        self.pool.run(self.handler.on_disconnect())

    def get_central_id(self) -> str:
        return f"central.{self.device_id}"
