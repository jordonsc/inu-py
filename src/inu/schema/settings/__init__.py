from .. import Schema
from ... import error
from ...const import DeviceType


class Settings(Schema):
    """
    Base class for all settings.
    """
    heartbeat_interval: int = 5
    heartbeat_interval_hint: str = "Time in seconds to broadcast a device heartbeat (1 to 60)"
    heartbeat_interval_min: int = 1
    heartbeat_interval_max: int = 60

    listen_subjects: str = ""
    listen_subjects_hint: str = "Will respond to messages (such as triggers) from subjects matching these strings; " \
                                "space delimited"


class CooldownDevice:
    """
    Device has a cool-down period after execution.
    """
    cooldown_time: int = 5000
    cooldown_time_hint: str = "Time in ms before the device will reactivate"
    cooldown_time_min: int = 0


class Relay(Settings):
    """
    ## An on-off or timer based power relay.

    If `auto_off` is set, the device will automatically turn itself back off after `time_delay` seconds.

    If `allow_toggle` is set, the device will act as a toggle and can be turned off by a second trigger command.
    """
    auto_off: bool = False
    auto_off_hint: str = "Automatically turn the switch off after `time_delay` seconds"

    allow_toggle: bool = False
    allow_toggle_hint: str = "Triggers will either turn the device on or off, based on the current state."

    time_delay: int = 30
    time_delay_hint: str = "Time to switch the device off after triggering in seconds"
    time_delay_min: int = 0


def get_device_type_from_id(device_id: str) -> str:
    """
    Returns the device type from a device ID.

    "motion.foo" -> "motion"
    """
    parts = device_id.split(".")
    if len(parts) < 2:
        raise error.InvalidDeviceId()

    device_type = parts[0].strip().lower()
    # validate device type -
    get_device_settings_class(device_type)

    return device_type


def get_device_settings_class(dvc: str) -> type:
    """
    Find the correct settings class for the given device type.
    """
    from . import sensors, actuators

    if dvc == DeviceType.MOTION:
        return sensors.MotionSensor
    elif dvc == DeviceType.RANGE:
        return sensors.RangeTrigger
    elif dvc == DeviceType.ACTUATOR:
        return actuators.Actuator
    elif dvc == DeviceType.DOOR:
        return actuators.Door
    elif dvc == DeviceType.RELAY:
        return Relay
    else:
        raise error.UnsupportedDeviceType(f"Unsupported device type: {dvc}")


def get_hint_for_settings_class(settings_class) -> str:
    hint = ""
    doc = settings_class.__doc__ or ""
    for line in doc.strip().split("\n"):
        line = line.strip()

        if len(hint) > 0:
            hint += "\n" + line.strip()
        else:
            hint = line.strip()

    return hint


def get_config_for_settings_class(settings_class) -> dict[str, (str, str, int | None, int | None)]:
    config = {}

    def add_class(cls: type):
        if '__annotations__' not in cls.__dict__:
            return

        for base in cls.__bases__:
            add_class(base)

        for k, v in cls.__dict__['__annotations__'].items():
            if k[-5:] == "_hint" or k[-4:] == "_min" or k[-4:] == "_max":
                continue

            if f"{k}_hint" in cls.__dict__:
                hint = cls.__dict__[f"{k}_hint"]
            else:
                hint = ""

            if f"{k}_min" in cls.__dict__:
                conf_min = cls.__dict__[f"{k}_min"]
            else:
                conf_min = None

            if f"{k}_max" in cls.__dict__:
                conf_max = cls.__dict__[f"{k}_max"]
            else:
                conf_max = None

            config[k] = (v.__name__, hint, conf_min, conf_max)

    add_class(settings_class)

    return config


def get_config_for_device(device_type: str) -> (str, dict[str, (str, str, int | None, int | None)]):
    """
    Returns both the device type hint and a dictionary of settings.
    """
    cls = get_device_settings_class(device_type)
    return get_hint_for_settings_class(cls), get_config_for_settings_class(cls)
