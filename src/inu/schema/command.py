from . import Schema


class Command(Schema):
    pass


class Trigger(Command):
    code: int = None


class Jog(Command):
    device_id: str = None
    distance: int = 0
    speed: int = 0


class Ota(Command):
    version: int = None


class Reboot(Command):
    pass
