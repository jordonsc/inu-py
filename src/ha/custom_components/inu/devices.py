import time

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.entity import DeviceInfo
from inu_net import Status
from inu_net.const import INU_BUILD


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

        self.sensor_active = None
        self.sensor_enabled = None
        self.sensor_locked = None

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


class StateField:
    ACTIVE = "active"
    ENABLED = "enabled"
    LOCKED = "locked"


class InuStateSensor(BinarySensorEntity):
    def __init__(self, device: Device, state_field: str):
        self.state_field = state_field
        self.device = device
        self.entity_id = f"binary_sensor.{clean_device_id(device.device_id)}_{state_field}"
        self._attr_name = f"Inu {device.device_id}: {state_field}"
        self._attr_unique_id = self.entity_id

        if self.state_field == StateField.ACTIVE:
            self._attr_icon = "mdi:bell-ring-outline"
        elif self.state_field == StateField.ENABLED:
            self._attr_icon = "mdi:check-circle-outline"
        elif self.state_field == StateField.LOCKED:
            self._attr_icon = "mdi:lock-outline"

    def update(self) -> None:
        pass

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

    @property
    def device_info(self) -> DeviceInfo | None:
        return DeviceInfo(
            identifiers={("inu", self.device.device_id)},
            name=self.device.device_id,
            manufacturer="Inu",
            model=self.device.device_id.split(".")[0],
            sw_version=INU_BUILD,
        )
