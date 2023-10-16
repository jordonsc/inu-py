from . import Schema
from ..error import Malformed


class Status(Schema):
    active: bool = None
    status: str = None

    def _validate(self):
        if self.active is None:
            raise Malformed("Active cannot be None")
