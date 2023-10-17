import asyncio
import time

from inu import const
from inu.app import InuApp
from inu.hardware.sonar import Sonar
from inu.schema.settings.sensors import RangeTrigger
from micro_nats.util.asynchronous import TaskPool


class RangeApp(InuApp):
    TYPE_SONAR = "sonar"

    class SensorState:
        IDLE = 0  # Normal state, no activity
        HOT = 1  # Sensor is below range threshold, but not time threshold
        ACTIVE = 2  # Sensor has fired, and remains inside range threshold
        COOLDOWN = 3  # Sensor did fire, is in a cooling off period before allowing another trigger

    def __init__(self):
        super().__init__(RangeTrigger)
        self.pool = TaskPool()
        self.range_type = self.get_config(["range", "type"])

        if self.range_type == self.TYPE_SONAR:
            self.sensor = Sonar(
                uart=1,
                tx=self.get_config(["range", "tx"], 33),
                rx=self.get_config(["range", "rx"], 38)
            )
        else:
            raise NotImplemented(f"Ranging sensor type '{self.range_type}' not supported")

    async def main_loop(self):
        """
        Endless app loop.
        """
        await self.init()

        self.pool.run(self.sensor.read_loop())

        state = self.SensorState.IDLE
        state_changed = 0

        def set_state(s):
            nonlocal state, state_changed
            state = s
            state_changed = time.time()

        while True:
            await self.on_loop()
            await asyncio.sleep(0.1)

            distance = self.sensor.get_distance()

            if state == self.SensorState.IDLE:
                # Idle, can trigger
                if distance <= self.inu.settings.max_distance:
                    if self.inu.settings.wait_delay == 0:
                        # No wait delay, fire immediately
                        set_state(self.SensorState.ACTIVE)
                        await self.fire()
                    else:
                        set_state(self.SensorState.HOT)

            elif state == self.SensorState.HOT:
                # Range dropped below threshold
                if distance > self.inu.settings.max_distance:
                    set_state(self.SensorState.IDLE)
                else:
                    if time.time() - state_changed > (self.inu.settings.wait_delay / 1000):
                        # Sensor under range for required threshold, fire
                        set_state(self.SensorState.ACTIVE)
                        await self.fire()

            elif state == self.SensorState.ACTIVE:
                # Sensor must return to normal before allowing it to return to idle state
                if distance > self.inu.settings.max_distance:
                    set_state(self.SensorState.COOLDOWN)

            elif state == self.SensorState.COOLDOWN:
                # In cooldown, return to normal after expiry
                if time.time() - state_changed > (self.inu.settings.cooldown_time / 1000):
                    set_state(self.SensorState.IDLE)

    async def fire(self):
        self.logger.info(f"Firing with range {self.sensor.get_distance()}; code {self.inu.settings.trigger_code}")
        await self.inu.command(const.Subjects.COMMAND_TRIGGER, {
            'code': self.inu.settings.trigger_code,
            'range': self.sensor.get_distance(),
        })


if __name__ == "__main__":
    app = RangeApp()
    asyncio.run(app.main_loop())
