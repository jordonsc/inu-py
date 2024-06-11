from . import Control
from inu import error

from ..colour import ColourCode


class Colour(Control):
    """
    Set device colour & brightness.

    COL <colour <!>

    colour - #RRGGBB[XX] or R,G,B[,X]
    ! - required to commit the change
    """
    CONTROL_CODE = "COL"
    ALIASES = ["COL", "COLOUR", "COLOR"]

    def __init__(self, ctrl: str = None):
        super().__init__(ctrl)

        if self.code not in self.ALIASES or 1 > len(self.args) > 2:
            raise error.Malformed(f"Invalid {self.CONTROL_CODE} control: {ctrl}")

        self.colour = ColourCode(self.args[0])

    def __repr__(self):
        return f"COL {self.colour}"


class Fx(Control):
    """
    LED FX control.

    FX <colour> <duration> <fx>

    colour - #RRGGBB[XX] or R,G,B[,X]
    duration - time in milliseconds
    FX - one of: FADE, SLIDEL, SLIDER, PULSEL, PULSER
    """
    CONTROL_CODE = "FX"

    class FX:
        FADE = "FADE"
        SLIDE_L = "SLIDEL"
        SLIDE_R = "SLIDER"
        PULSE_L = "PULSEL"
        PULSE_R = "PULSER"

    def __init__(self, ctrl: str = None):
        super().__init__(ctrl)

        if len(self.args) != 3:
            raise error.Malformed(f"Invalid {self.CONTROL_CODE} control: {ctrl}")

        self.colour = ColourCode(self.args[0])

    def get_duration(self) -> int:
        """
        Get the duration value in milliseconds.
        """
        return int(self.args[1])

    def get_fx(self) -> str:
        """
        Get the FX value.
        """
        fx = self.args[2].upper().strip()
        if fx not in [self.FX.FADE, self.FX.SLIDE_L, self.FX.SLIDE_R, self.FX.PULSE_L, self.FX.PULSE_R]:
            return self.FX.FADE
        else:
            return fx

    def __repr__(self):
        return f"FX {self.colour} -> {self.get_fx()}"
