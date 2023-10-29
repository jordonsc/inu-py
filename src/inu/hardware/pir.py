import asyncio
import logging

from machine import Pin
from ..hardware import MotionSensor


class Pir(MotionSensor):
    def __init__(self, pin: int = 33, pull_mode: int = None):
        self.logger = logging.getLogger('inu.hw.pir')
        self.motion = False
        self.pin = Pin(pin, Pin.IN, pull=pull_mode)

    async def read_loop(self):
        while True:
            self.motion = self.pin.value() == 1
            await asyncio.sleep(0.01)

    def is_motion(self) -> bool:
        return self.motion
