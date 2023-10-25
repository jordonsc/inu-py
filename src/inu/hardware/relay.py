import logging

from machine import Pin


class Relay:
    def __init__(self, pin: int = 33, ground: int = None, on_state_change: callable = None):
        self.logger = logging.getLogger('inu.hw.relay')
        self.active = False
        self.state_cb = on_state_change

        self.pin = Pin(pin, Pin.OUT)
        self.pin.off()

        if ground:
            self.ground = Pin(ground, Pin.IN)
        else:
            self.ground = None

    async def on(self):
        self.pin.on()
        self.logger.debug(f"Relay:{self.pin} ACTIVE")

        if self.state_cb:
            await self.state_cb(True)

    async def off(self):
        self.pin.off()
        self.logger.debug(f"Relay:{self.pin} INACTIVE")

        if self.state_cb:
            await self.state_cb(False)

    async def toggle(self):
        if self.active:
            await self.off()
        else:
            await self.on()

    def is_active(self) -> bool:
        return self.active
