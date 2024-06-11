from apa102 import Apa102 as LedStrip
from . import RoboticsDevice
from .control import Control
from .control.lights import Colour, Fx


class Apa102(RoboticsDevice):
    """
    APA102 LED strip.
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
            # Fill the strip/segment fully & instantly with a single colour
            self.leds.fill(ctrl.colour, write=ctrl.execute)
        elif isinstance(ctrl, Fx):
            # Fx transitions -
            if ctrl.get_fx() == Fx.FX.FADE:
                # Full segment fade to colour
                self.leds.fade(ctrl.colour, ctrl.get_duration())
            elif ctrl.get_fx() == Fx.FX.SLIDE_L:
                # Slide "left"
                self.leds.slide(ctrl.colour, ctrl.get_duration(), direction=LedStrip.DIRECTION.LEFT)
            elif ctrl.get_fx() == Fx.FX.SLIDE_R:
                # Slide "right"
                self.leds.slide(ctrl.colour, ctrl.get_duration(), direction=LedStrip.DIRECTION.RIGHT)
            elif ctrl.get_fx() == Fx.FX.PULSE_L:
                # Pulse "left"
                self.leds.pulse(ctrl.colour, ctrl.get_duration(), direction=LedStrip.DIRECTION.LEFT)
            elif ctrl.get_fx() == Fx.FX.PULSE_R:
                # Pulse "right"
                self.leds.pulse(ctrl.colour, ctrl.get_duration(), direction=LedStrip.DIRECTION.RIGHT)

    def select_component(self, component_id):
        self.leds.select_segment(component_id)

    def __repr__(self):
        return f"APA102 strip"
