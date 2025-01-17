from __future__ import annotations

import logging
import random

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import device_registry

from inu_net import Inu, const, InuHandler
from inu_net.schema import Heartbeat
from inu_net.schema.status import Status

from micro_nats import error as mn_error, model
from micro_nats.jetstream.error import ErrorResponseException
from micro_nats.jetstream.protocol.consumer import Consumer, ConsumerConfig
from micro_nats.util import Time
from .devices import Device, InuStateSensor, StateField, InuStateSwitch, InuStateText, InuTriggerButton, clean_device_id


class Hub(InuHandler):
    manufacturer = "Inu Networks"

    def __init__(self, ha: HomeAssistant, host: str) -> None:
        self.ha = ha
        self.host = host
        self.id = host.lower()
        self.dr = device_registry.async_get(ha)

        self.add_sensor_callback = None
        self.add_button_callback = None
        self.add_text_callback = None
        self.add_switch_callback = None

        self.has_inited = False

        self.logger = logging.getLogger('inu.hub')

        self.inu = Inu(const.Context(
            device_id=["hass", f"i{random.randint(1000, 9999)}"],
            nats_server=host,
        ), self)

        self.device_pool = {}
        self.consumers = [
            (const.Streams.HEARTBEAT, const.Subjects.HEARTBEAT, self.on_hb),
            (const.Streams.COMMAND, const.Subjects.COMMAND, self.on_command),
            (const.Streams.STATUS, const.Subjects.STATUS, self.on_status),
        ]

    @property
    def hub_id(self) -> str:
        return self.id

    @callback
    def nats_service(self, call: ServiceCall) -> None:
        self.ha.async_create_task(self.publish(call.data["subject"], call.data["payload"]))

    async def publish(self, subject: str, payload: str) -> None:
        """
        Publish a message to the Inu server.
        """
        self.logger.warning(f"NATS publish: subj: {subject}, payload: {payload}")
        await self.inu.nats.publish(subject, str(payload))

    async def test_connection(self) -> bool:
        if not self.has_inited:
            await self.inu.init()
        return self.inu.nats.is_connected()

    def is_device_active(self, device_id: str) -> bool:
        """
        Check if a device is active.
        """
        if device_id not in self.device_pool:
            return False

        return self.device_pool[device_id].status.active

    def is_device_locked(self, device_id: str) -> bool:
        """
        Check if a device is locked.
        """
        if device_id not in self.device_pool:
            return False

        return self.device_pool[device_id].status.locked

    def is_device_enabled(self, device_id: str) -> bool:
        """
        Check if a device is enabled.
        """
        if device_id not in self.device_pool:
            return False

        return self.device_pool[device_id].status.enabled

    async def on_connect(self, server: model.ServerInfo):
        self.logger.info("Connected to Inu server")
        ack_wait = Time.sec_to_nano(3)

        try:
            for stream_name, subj, cb in self.consumers:
                self.logger.debug(f"Subscribing to Inu stream '{stream_name}'")
                await self.inu.js.consumer.create(
                    Consumer(stream_name, ConsumerConfig(
                        filter_subject=const.Subjects.all(subj),
                        deliver_policy=ConsumerConfig.DeliverPolicy.NEW,
                        ack_wait=ack_wait,
                    )), cb,
                )

        except mn_error.NotFoundError:
            self.logger.error("Stream not found. Is Inu server fully online?")
            return

        except ErrorResponseException as e:
            err = e.err_response
            self.logger.error(f"INU: {err.code}-{err.err_code}: {err.description}")

        except Exception as e:
            self.logger.error(f"Inu subscribe error: {type(e).__name__}: {e}")
            return

    async def on_hb(self, msg: model.Message):
        """
        Heartbeat from a device. Used to track when a device goes offline.
        """
        await self.inu.js.msg.ack(msg)
        device_id = msg.get_subject()[len(const.Subjects.HEARTBEAT) + 1:]
        hb = Heartbeat(msg.get_payload())

        if device_id in self.device_pool:
            # if we were first detected by a status update, we might not have a heartbeat frequency
            if self.device_pool[device_id].heartbeat_freq == -1:
                self.device_pool[device_id].heartbeat_freq = hb.interval

            # update the heartbeat time
            self.device_pool[device_id].beat()
        else:
            dvc = Device(device_id, hb_freq=hb.interval)
            self.device_pool[device_id] = dvc
            self.logger.warning(f"Device <{device_id}> now online (heartbeat)")
            await self.add_device(dvc)

    async def on_status(self, msg: model.Message):
        """
        Device change state.
        """
        await self.inu.js.msg.ack(msg)
        device_id = msg.get_subject()[len(const.Subjects.STATUS) + 1:]
        status = Status(msg.get_payload())

        if device_id in self.device_pool:
            self.device_pool[device_id].status = status
            self.device_pool[device_id].update_ha()
        else:
            dvc = Device(device_id, hb_freq=-1)
            dvc.status = status
            self.device_pool[device_id] = dvc
            self.logger.warning(f"Device <{device_id}> now online (status update)")
            await self.add_device(dvc)

    async def on_command(self, msg: model.Message):
        """
        Command (eg trigger). Send to logging tool.
        """
        await self.inu.js.msg.ack(msg)
        subj = msg.get_subject()[len(const.Subjects.COMMAND) + 1:].split(".", 1)
        cmd = subj[0]
        device_id = subj[1]

        # send push message for a trigger
        if cmd == "trigger":
            self.logger.info(f"Device <{device_id}> triggered")

    async def add_device(self, device: Device):
        """
        Register a newly-detected Inu device as a Home Assistant entity.
        """
        if (self.add_sensor_callback is None or self.add_text_callback is None or
                self.add_switch_callback is None or self.add_button_callback is None):
            # reset the device pool so it can be added later
            self.logger.error("Attempted to add a device without appropriate callbacks")
            self.device_pool = {}
            return

        self.logger.warning(f"inu: adding device '{device.device_id}'")

        # 'Active' state is a read-only binary sensor
        device.binary_sensor_active = InuStateSensor(device, StateField.ACTIVE)

        self.add_sensor_callback([
            device.binary_sensor_active,
        ])

        # 'Enabled' and 'Locked' states are read-write switches
        device.sensor_active = InuStateSwitch(device, self.inu, StateField.ACTIVE)
        device.sensor_enabled = InuStateSwitch(device, self.inu, StateField.ENABLED)
        device.sensor_locked = InuStateSwitch(device, self.inu, StateField.LOCKED)

        self.add_switch_callback([
            device.sensor_active,
            device.sensor_enabled,
            device.sensor_locked,
        ])

        # 'Status' is a read-only text sensor
        device.sensor_status = InuStateText(device)

        self.add_text_callback([
            device.sensor_status,
        ])

        # Trigger button sends a TRG with code 0 to the device's central address
        device.trigger_button = InuTriggerButton(device, self.inu)

        self.add_button_callback([
            device.trigger_button,
        ])
