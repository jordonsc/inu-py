from apa102 import Apa102 as LedStrip
from . import Control
from ..robotics import RoboticsDevice, Colour, Fx


class Apa102(RoboticsDevice):
    """
    APA102[c] LED strip.
    """
    CONFIG_ALIASES = ["apa102", "apa102c"]

    def __init__(self, num_leds: int, spi_index=1, segments=None, inu=None):
        """
        """
        super().__init__(inu=inu, log_path="inu.robotics.apa102")
        self.leds = LedStrip(num_leds, spi_index=spi_index)

        if segments is not None:
            for seg_id, (start, end) in segments.items():
                self.leds.create_segment(seg_id, start, end)

    async def execute(self, ctrl: Control, reverse: bool = False):
        await super().execute(ctrl)

        if isinstance(ctrl, Colour):
            self.leds.fill(ctrl.get_r(), ctrl.get_g(), ctrl.get_b(), ctrl.get_brightness(), write=ctrl.execute)
        elif isinstance(ctrl, Fx):
            self.leds.fade(ctrl.get_r(), ctrl.get_g(), ctrl.get_b(), 31, ctrl.get_duration())

    def select_component(self, component_id):
        self.leds.select_segment(component_id)

    def __repr__(self):
        return f"APA102 strip"