import logging
import time

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.components.button import ButtonEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.components.text import TextEntity
from homeassistant.helpers.entity import DeviceInfo
from inu_net import Status, Inu, const
from inu_net.schema.command import Trigger

DOMAIN = "inu"
MANUFACTURER = "Inu Networks"


def clean_device_id(device_id: str) -> str:
    """
    Clean a device ID to be used as an entity ID.
    """
    return device_id.replace(".", "_").replace("-", "_")


class Device:
    def __init__(self, device_id: str, hb_freq: int):
        self.device_id = device_id
        self.heartbeat_freq = hb_freq
        self.last_heartbeat = time.monotonic()

        self.status = Status()
        self.status.enabled = False
        self.status.locked = False
        self.status.active = False

        self.binary_sensor_active = None
        self.sensor_active = None
        self.sensor_enabled = None
        self.sensor_locked = None
        self.sensor_status = None
        self.trigger_button = None

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

    def update_ha(self):
        if self.sensor_enabled is not None:
            self.sensor_enabled.schedule_update_ha_state()

        if self.sensor_active is not None:
            self.sensor_active.schedule_update_ha_state()

        if self.sensor_locked is not None:
            self.sensor_locked.schedule_update_ha_state()

        if self.sensor_status is not None:
            self.sensor_status.schedule_update_ha_state()


class StateField:
    ACTIVE = "active"
    ENABLED = "enabled"
    LOCKED = "locked"


class InuEntity:
    def __init__(self, device: Device, inu: Inu = None):
        self.entity_id = None
        self.device = device
        self.inu = inu

    @property
    def unique_id(self) -> str | None:
        return self.entity_id

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id)},
            manufacturer=MANUFACTURER,
            model=self.device.device_id.split(".")[0],
            name=self.device.device_id,
        )


class InuStateSensor(InuEntity, BinarySensorEntity):
    def __init__(self, device: Device, state_field: str):
        super().__init__(device)
        self.state_field = state_field
        self.entity_id = f"binary_sensor.{clean_device_id(device.device_id)}_{state_field}"
        self._attr_name = f"Inu {device.device_id}: {state_field}"
        device_type = self.device.device_id.split(".")[0]

        if device_type == "radar" or device_type == "motion" or device_type == "range":
            self._attr_device_class = BinarySensorDeviceClass.MOTION
            self._attr_icon = "mdi:motion-sensor"
        else:
            self._attr_device_class = BinarySensorDeviceClass.RUNNING
            self._attr_icon = "mdi:check-circle-outline"

    @property
    def is_on(self) -> bool | None:
        return self.device.status.active

class InuStateSwitch(InuEntity, SwitchEntity):
    def __init__(self, device: Device, inu: Inu, state_field: str):
        super().__init__(device, inu)
        self.state_field = state_field
        self.entity_id = f"switch.{clean_device_id(device.device_id)}_{state_field}"
        self._attr_name = f"Inu {device.device_id}: {state_field}"

        if self.state_field == StateField.ACTIVE:
            self._attr_icon = "mdi:bell-ring-outline"
        elif self.state_field == StateField.ENABLED:
            self._attr_icon = "mdi:check-circle-outline"
        elif self.state_field == StateField.LOCKED:
            self._attr_icon = "mdi:lock-outline"

    @property
    def is_on(self) -> bool | None:
        if self.state_field == StateField.ACTIVE:
            return self.device.status.active
        elif self.state_field == StateField.ENABLED:
            return self.device.status.enabled
        elif self.state_field == StateField.LOCKED:
            return self.device.status.locked
        else:
            return False

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        code = 0
        if self.state_field == StateField.ENABLED:
            code = const.TriggerCode.ENABLE_ON
        elif self.state_field == StateField.LOCKED:
            code = const.TriggerCode.LOCK_ON

        await self.send_trigger(code)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        code = 0
        if self.state_field == StateField.ACTIVE:
            code = const.TriggerCode.BREAK
        elif self.state_field == StateField.ENABLED:
            code = const.TriggerCode.ENABLE_OFF
        elif self.state_field == StateField.LOCKED:
            code = const.TriggerCode.LOCK_OFF

        await self.send_trigger(code)

    async def send_trigger(self, code: int) -> None:
        if not self.inu.nats.is_connected():
            return

        trg = Trigger()
        trg.code = code

        await self.inu.nats.publish(
            const.Subjects.fqs(
                [const.Subjects.COMMAND, const.Subjects.COMMAND_TRIGGER],
                f"central.{self.device.device_id}"
            ), trg.marshal()
        )


class InuStateText(InuEntity, TextEntity):
    def __init__(self, device: Device):
        super().__init__(device)
        self.entity_id = f"text.{clean_device_id(device.device_id)}_status"
        self._attr_name = f"Inu {device.device_id}: status"
        self._attr_icon = "mdi:folder-text-outline"
        self._attr_native_min = 0
        self._attr_native_max = 255

    @property
    def native_value(self) -> str | None:
        """Return the value reported by the text."""
        return self.device.status.status if self.device.status.status is not None else ""


class InuTriggerButton(InuEntity, ButtonEntity):
    def __init__(self, device: Device, inu: Inu):
        super().__init__(device, inu)
        self.entity_id = f"button.{clean_device_id(device.device_id)}_trigger"
        self._attr_name = f"Inu {device.device_id}: trigger"
        self._attr_icon = "mdi:gesture-tap-button"

    def press(self) -> None:
        """Press the button."""
        logging.warning(f"Device <{self.device.device_id}> NON-ASYNC triggered")
        raise NotImplementedError()

    async def async_press(self) -> None:
        """Press the button."""
        logging.warning(f"Device <{self.device.device_id}> triggered")
        await self.send_trigger(0)
        logging.warning(f"Device <{self.device.device_id}> sent trigger")

    async def send_trigger(self, code: int) -> None:
        if not self.inu.nats.is_connected():
            return

        trg = Trigger()
        trg.code = code

        await self.inu.nats.publish(
            const.Subjects.fqs(
                [const.Subjects.COMMAND, const.Subjects.COMMAND_TRIGGER],
                f"central.{self.device.device_id}"
            ), trg.marshal()
        )
