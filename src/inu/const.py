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


class DeviceType:
    # Generic utility, such as a CLI, settings editor, bootstrap, etc
    UTILITY = "utility"

    # Monitor application, log viewer, etc
    MONITOR = "monitor"

    # On-off or timer switch - can be triggered by sensors, etc
    RELAY = "relay"

    # Motion, light, distance, etc sensors
    MOTION = "motion"
    RANGE = "range"

    # Motorised actuator or physical pulley, winch, etc
    ACTUATOR = "actuator"
    DOOR = "door"


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
    # {'active': bool, 'status': str}
    STATUS = 'status'

    # Commands require action from other devices, such as a trigger
    # {...}
    COMMAND = 'cmd'
    COMMAND_SUB = {
        # trigger may include sensor parameters, like distance, light level, motion level, etc
        'trigger',
    }

    # Heartbeats let a controller know that you're still alive and detect devices going offline
    # {'uptime': int64}
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
