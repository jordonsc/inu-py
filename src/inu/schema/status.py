from . import Schema
from ..error import Malformed


class Status(Schema):
    enabled: bool = None
    active: bool = None
    locked: bool = None
    status: str = None

    def _validate(self):
        if self.enabled is None:
            raise Malformed("'enabled' cannot be None")

        if self.active is None:
            raise Malformed("'active' cannot be None")

    def __repr__(self):
        return f"enabled={self.enabled} locked={self.locked} active={self.active} status=\"{self.status}\""

    def can_act(self, allow_active=False):
        """
        Check if the state is suitable for a device to act (eg. on a trigger)

        Returns True if the device is enabled, not locked and not active.
        """
        if not allow_active and self.active:
            return False

        return self.enabled and not self.locked
