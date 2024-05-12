import asyncio
import time

import machine
from inu import const

from inu.app import InuApp
from inu.schema.settings.sensors import Capacitor as CapacitorSettings


class CapacitorApp(InuApp):
    # Sensor polling rate in seconds
    POLL_RATE = 0.05

    # Percentile delta of value, or time between change reports
    REPORT_CHANGE = 1
    REPORT_MAX_TIME = 5

    def __init__(self):
        super().__init__(CapacitorSettings)
        self.sensor = machine.TouchPad(machine.Pin(self.get_config(["sensor", "pin"], 8), machine.Pin.IN))
        self.last_poll = time.time()
        self.active = False
        self.new_state = False

        # Time we've been in a new state (for sensitivity delays)
        self.state_change_time = 0

        # For updating the device status - value/time we last reported
        self.last_reported_value = 0
        self.last_reported_time = time.time()

        # For refire delay - time since we last sent a trigger
        self.active_since = 0

    async def app_init(self):
        await self.set_state_from_last()

    async def app_tick(self):
        if time.time() - self.last_poll < self.POLL_RATE:
            return

        try:
            # Poll the capacitive sensor
            self.last_poll = time.time()
            raw_value = self.sensor.read()
            self.logger.info(f"Raw sensor value: {raw_value}")
            value = self.map_value(raw_value, self.inu.settings.sensor_low, self.inu.settings.sensor_high, 0, 100)

            # Report if the value has changed by at least REPORT_CHANGE percent
            if self.last_reported_value == 0:
                report_state = True
            else:
                if time.time() - self.last_reported_time > self.REPORT_MAX_TIME:
                    report_state = True
                else:
                    report_state = abs(value - self.last_reported_value) > self.REPORT_CHANGE

            # Work out in which orientation we activate or deactivate the trigger
            if self.inu.settings.trigger_on < self.inu.settings.trigger_off:
                do_activate = value < self.inu.settings.trigger_on
                do_deactivate = value > self.inu.settings.trigger_off
            else:
                do_activate = value > self.inu.settings.trigger_on
                do_deactivate = value < self.inu.settings.trigger_off

            # Delay-wait before activating or deactivating
            if do_activate and not self.active:
                if self.new_state:
                    if time.time() - self.state_change_time >= (self.inu.settings.delay_wait / 1000):
                        self.active = True
                        report_state = True
                        await self.fire()
                else:
                    self.new_state = True
                    self.state_change_time = time.time()

            elif do_deactivate and self.active:
                if not self.new_state:
                    if time.time() - self.state_change_time >= (self.inu.settings.delay_wait / 1000):
                        self.active = False
                        report_state = True
                else:
                    self.new_state = False
                    self.state_change_time = time.time()

            # Update device state
            if report_state:
                await self.inu.status(active=self.active, status=f"{value:.1f}% ({raw_value})")
                self.logger.debug(f"Sensor value: {value:.1f}% ({raw_value})")
                self.last_reported_value = value
                self.last_reported_time = time.time()

            # Trigger a refire
            can_refire = (self.inu.settings.refire_delay > 0) and self.active
            if can_refire and time.time() - self.active_since > (self.inu.settings.refire_delay / 1000):
                await self.fire()

        except Exception as e:
            self.logger.error(f"Error in app_tick: {e}")

    async def fire(self):
        """
        Dispatch a trigger and update the time that we last triggered.
        """
        self.active_since = time.time()
        await self.inu.command(const.Subjects.COMMAND_TRIGGER, {
            'code': self.inu.settings.trigger_code,
        })


if __name__ == "__main__":
    app = CapacitorApp()
    asyncio.run(app.run())
