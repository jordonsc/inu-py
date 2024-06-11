from . import Control
from inu import error


class Move(Control):
    """
    Move the device, such as an actuator, by a given distance at a given speed.

    MV <distance> <speed>
    """
    CONTROL_CODE = "MV"
    ALIASES = ["M", "MV", "MOVE"]

    def __init__(self, ctrl: str = None):
        super().__init__(ctrl)

        if self.code not in self.ALIASES or len(self.args) != 2:
            raise error.Malformed(f"Invalid {self.CONTROL_CODE} control: {ctrl}")

    def get_distance(self) -> int:
        """
        Distance of the move operation, in mm.
        """
        return int(self.args[0])

    def get_speed(self) -> int:
        """
        Speed to move the actuator in mm/s.
        """
        return int(self.args[1])

    def __repr__(self):
        return f"MV {self.get_distance()} mm @ {self.get_speed()} mm/s"
