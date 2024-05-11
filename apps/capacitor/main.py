import asyncio
import time

import machine

from inu.app import InuApp
from inu.schema.settings.sensors import Capacitor as CapacitorSettings


class CapacitorApp(InuApp):
    POLL_RATE = 0.5

    def __init__(self):
        super().__init__(CapacitorSettings)
        self.sensor = machine.TouchPad(machine.Pin(self.get_config(["sensor", "pin"], 8), machine.Pin.IN))
        self.last_poll = time.time()
        self.active = False

    async def app_init(self):
        await self.set_state_from_last()

    async def app_tick(self):
        if time.time() - self.last_poll < self.POLL_RATE:
            return

        # Poll the capacitive sensor
        self.last_poll = time.time()
        raw_value = self.sensor.read()
        value = round(self.map_value(raw_value, self.inu.settings.sensor_low, self.inu.settings.sensor_high, 0, 100), 2)
        self.logger.info(f"Sensor value: {raw_value} -> {value}%")

        # Work out in which orientation we activate or deactivate the trigger
        if self.inu.settings.trigger_on < self.inu.settings.trigger_off:
            do_activate = value < self.inu.settings.trigger_on
            do_deactivate = value > self.inu.settings.trigger_off
        else:
            do_activate = value > self.inu.settings.trigger_on
            do_deactivate = value < self.inu.settings.trigger_off

        # Fire status updates
        if do_activate and not self.active:
            self.active = True
            await self.on_trigger(self.inu.settings.trigger_code)
            await self.inu.status(active=True, status=f"{value}%")

        elif do_deactivate and self.active:
            self.active = False
            await self.on_trigger(self.inu.settings.trigger_code)
            await self.inu.status(active=False, status='')

        elif self.active:
            await self.inu.status(status=f"{value}%")


if __name__ == "__main__":
    app = CapacitorApp()
    asyncio.run(app.run())
