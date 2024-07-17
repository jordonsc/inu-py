INU_BUILD = 46


class LogLevel:
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    FATAL = "fatal"


class Priority:
    P1 = 1
    P2 = 2
    P3 = 3
    P4 = 4
    P5 = 5

    HIGHEST = 1
    LOWEST = 5


class DeviceType:
    # Generic utility, such as a CLI, settings editor, bootstrap, etc
    UTILITY = "utility"

    # Monitor application, log viewer, etc
    MONITOR = "monitor"

    # On-off or timer switch - can be triggered by sensors, etc
    RELAY = "relay"

    # Physical switch(es)
    SWITCH = "switch"

    # Capacitive sensor
    CAPACITOR = "capacitor"

    # Motion, light, distance, etc sensors
    MOTION = "motion"
    RANGE = "range"
    LIGHT = "light"

    # Motorised actuator or physical pulley, winch, etc
    ROBOTICS = "robotics"


class Context:
    device_id: str | list[str] = None
    nats_server: str = None
    has_heartbeat: bool = False
    settings_class: type = None
    io_timeout: float = 3

    def __init__(self, device_id: str | list[str], **params):
        self.device_id = device_id

        for k, v in params.items():
            if k[0] == '_':
                continue
            setattr(self, k, v)


class Subjects:
    """
    Subject format should include the base subject + the device name:
        inu.log.some-sensor

    In addition, some subjects might have sub-subjects:
        inu.cmd.trigger.some-sensor

    Payloads are always JSON.
    """
    # Standard logging
    # '{'lvl': str, 'msg': str}
    # lvl: "debug", "info", "warning", "error", "fatal"
    LOG = 'log'

    # Alerts should raise human attention
    # {'priority': int8, 'msg': str}
    ALERT = 'alert'

    # Status updates, such as begin, end, etc
    # {'enabled': bool, 'active': bool, 'status': str}
    STATUS = 'status'

    # Base command, always requires a sub-command in the subject
    COMMAND = 'cmd'

    # Device has been activated, such as a button pressed or sensor trip
    # {'code': int}
    COMMAND_TRIGGER = 'trigger'

    # Jog a robotics actuator/servo - typically sent to the device's 'central' subject
    # {'device': str, 'distance': int, 'speed': int}
    COMMAND_JOG = 'jog'

    # Request a device perform an OTA update - must be sent to the device's 'central' subject
    # {'version': int}
    COMMAND_OTA = 'ota'

    # Request the device perform a soft or hard reboot
    # {}
    COMMAND_REBOOT = 'reboot'

    # Heartbeats let a controller know that you're still alive and detect devices going offline
    # Includes your build version and LAN IP address
    # {'uptime': int64, 'build': int, 'local_addr': str}
    HEARTBEAT = 'hb'

    # Settings define a device's configuration
    # {...}
    SETTINGS = 'settings'

    @staticmethod
    def all(subject: str | list[str], multi=True) -> str:
        """
        Get a wildcard subject.

        If `multi` is True, the wildcard will be >, otherwise it will use *.
        """
        wc = ">" if multi else "*"
        if isinstance(subject, list):
            subject = ".".join(subject)

        return ".".join([subject, wc])

    @staticmethod
    def fqs(subject: str | list[str], device: str | list[str]) -> str:
        """
        Get a fully-qualified subject string.
        """
        if isinstance(subject, list):
            subject = ".".join(subject)

        if isinstance(device, list):
            device = ".".join(device)

        return ".".join([subject, device])


class Streams:
    LOGS = 'logs'
    ALERTS = 'alerts'
    STATUS = 'status'
    COMMAND = 'commands'
    HEARTBEAT = 'heartbeats'
    SETTINGS = 'settings'


class TriggerCode:
    # [Robotics] Robotics interrupt - roll-back and restart
    INTERRUPT = 100
    # [Robotics] Request device recalibrate (must NOT be enabled)
    CALIBRATE = 101
    # Force-clear active state (repair lingering error without restarting)
    RESET_ACTIVE = 102
    # [Robotics] Similar to INTERRUPT, but will only reset the timer on an active WAIT command
    WAIT = 103
    # [Robotics] Will immediately drop out of an active WAIT command
    BREAK = 104

    ENABLE_TOGGLE = 110
    ENABLE_ON = 111
    ENABLE_OFF = 112

    LOCK_TOGGLE = 115
    LOCK_ON = 116
    LOCK_OFF = 117


class Strings:
    RANGE = "Range"
    SEQ = "Sequence"
    COOLDOWN = "Cooldown"
