from . import Schema


class Command(Schema):
    pass


class Trigger(Command):
    code: int = None
