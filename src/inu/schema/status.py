from . import Schema
from ..error import Malformed


class Status(Schema):
    enabled: bool = None
    active: bool = None
    status: str = None

    def _validate(self):
        if self.enabled is None:
            raise Malformed("'enabled' cannot be None")

        if self.active is None:
            raise Malformed("'active' cannot be None")

    def __repr__(self):
        return f"enabled={self.enabled} active={self.active} status=\"{self.status}\""
