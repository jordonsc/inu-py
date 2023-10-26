import asyncio
import time

from inu import const
from inu.app import InuApp
from inu.hardware.pir import Pir
from inu.schema.settings.sensors import MotionSensor
from micro_nats.util.asynchronous import TaskPool


class MotionApp(InuApp):
    TYPE_PIR = "pir"

    class SensorState:
        IDLE = 0  # Normal state, no activity
        ACTIVE = 1  # Sensor has fired and remains active
        COOLDOWN = 2  # Sensor did fire, is in a cooling off period before allowing another trigger

    def __init__(self):
        super().__init__(MotionSensor)
        self.pool = TaskPool()
        self.motion_type = self.get_config(["motion", "type"])

        if self.motion_type == self.TYPE_PIR:
            self.sensor = Pir(
                pin=self.get_config(["motion", "pin"], 33),
            )
        else:
            raise NotImplemented(f"Motion sensor type '{self.motion_type}' not supported")

    async def run(self):
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
            await self.app_tick()
            await asyncio.sleep(0.01)

            motion = self.sensor.is_motion()

            if state == self.SensorState.IDLE:
                # Idle, can trigger
                if motion:
                    self.inu.status(enabled=True, active=True)
                    await self.inu.set_state(self.SensorState.ACTIVE)
                    await self.fire()

            elif state == self.SensorState.ACTIVE:
                # Sensor must return to normal before allowing it to return to idle state
                if not motion:
                    await self.inu.status(enabled=True, active=False)
                    set_state(self.SensorState.COOLDOWN)

            elif state == self.SensorState.COOLDOWN:
                # In cooldown, return to normal after expiry
                if time.time() - state_changed > (self.inu.settings.cooldown_time / 1000):
                    set_state(self.SensorState.IDLE)

    async def fire(self):
        self.logger.info(f"Firing; code {self.inu.settings.trigger_code}")
        await self.inu.command(const.Subjects.COMMAND_TRIGGER, {
            'code': self.inu.settings.trigger_code,
        })


if __name__ == "__main__":
    app = MotionApp()
    asyncio.run(app.run())
