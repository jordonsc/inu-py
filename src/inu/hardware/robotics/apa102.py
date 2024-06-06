from apa102 import Apa102 as LedStrip
from . import Control
from ..robotics import RoboticsDevice, Colour


class Apa102(RoboticsDevice):
    """
    APA102[c] LED strip.
    """
    CONFIG_ALIASES = ["apa102", "apa102c"]

    def __init__(self, num_leds: int, spi_index=1, inu=None):
        """
        """
        super().__init__(inu=inu, log_path="inu.robotics.apa102")
        self.leds = LedStrip(num_leds, spi_index=spi_index)

    async def execute(self, ctrl: Control, reverse: bool = False):
        await super().execute(ctrl)

        if isinstance(ctrl, Colour):
            self.leds.fill(ctrl.get_r(), ctrl.get_g(), ctrl.get_b(), ctrl.get_brightness(), write=True)

    def __repr__(self):
        return f"APA102 strip"
