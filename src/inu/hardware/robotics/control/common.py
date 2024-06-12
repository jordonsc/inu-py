from . import Control
from inu import error


class Select(Control):
    """
    Select the active device. Should precede execution controls like MV.
    """
    CONTROL_CODE = "SEL"
    ALIASES = ["SEL", "S", "SELECT"]

    def __init__(self, ctrl: str = None):
        super().__init__(ctrl)

        if self.code not in self.ALIASES or len(self.args) != 1:
            raise error.Malformed(f"Invalid {self.CONTROL_CODE} control: {ctrl}")

    def get_device(self) -> str:
        """
        Returns the selection subject ("XX" from "SEL XX:YY").
        """
        return self.args[0].split(":")[0]

    def get_component(self) -> str:
        """
        Returns the selection component ("TT" from "SEL XX:YY").
        """
        return self.args[0].split(":")[1] if ":" in self.args[0] else None

    def allow_interrupt(self) -> bool:
        """
        Select Controls have no concept of interrupts but should not block the interrupt chain.
        """
        return True

    def __repr__(self):
        return f"SEL {self.get_device()}"


class Wait(Control):
    """
    Delay by a given time in milliseconds.

    The time can also be specified in seconds (s), minutes (m) or hours (h) by using the respective suffix.
    """
    CONTROL_CODE = "WAIT"
    ALIASES = ["W", "WAIT"]

    def __init__(self, ctrl: str = None):
        super().__init__(ctrl)

        if self.code not in self.ALIASES or len(self.args) != 1:
            raise error.Malformed(f"Invalid {self.CONTROL_CODE} control: {ctrl}")

        self.time = 0
        spec = self.args[0].upper().strip()

        if spec.endswith("S"):
            self.time = int(spec[:-1]) * 1000
        elif spec.endswith("M"):
            self.time = int(spec[:-1]) * 60 * 1000
        elif spec.endswith("H"):
            self.time = int(spec[:-1]) * 60 * 60 * 1000
        else:
            self.time = int(spec)

    def get_time(self) -> int:
        """
        Wait time as an integer in milliseconds.
        """
        return self.time

    def __repr__(self):
        return f"WAIT {self.get_time()}"


class Trigger(Control):
    """
    Send a Trigger code.
    """
    CONTROL_CODE = "TRG"
    ALIASES = ["TRG", "TRIGGER"]

    def __init__(self, ctrl: str = None):
        super().__init__(ctrl)

        if self.code not in self.ALIASES or len(self.args) != 1:
            raise error.Malformed(f"Invalid {self.CONTROL_CODE} control: {ctrl}")

    def get_code(self) -> int:
        """
        Trigger code as an integer.
        """
        return int(self.args[0])

    def __repr__(self):
        return f"TRG {self.get_code()}"
