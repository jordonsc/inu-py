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

        self.state = self.SensorState.IDLE
        self.state_changed = 0

        if self.motion_type == self.TYPE_PIR:
            self.sensor = Pir(
                pin=self.get_config(["motion", "pin"], 33),
            )
        else:
            raise NotImplemented(f"Motion sensor type '{self.motion_type}' not supported")

    async def app_init(self):
        self.pool.run(self.sensor.read_loop())
        await self.inu.status(enabled=True, active=False, status="")

    async def app_tick(self):
        def set_state(s):
            self.state = s
            self.state_changed = time.time()

        motion = self.sensor.is_motion()

        if self.state == self.SensorState.IDLE:
            # Idle, can trigger
            if motion and self.inu.state.enabled:
                await self.inu.activate()
                set_state(self.SensorState.ACTIVE)
                await self.fire()

        elif self.state == self.SensorState.ACTIVE:
            # Sensor must return to normal before allowing it to return to idle state
            if not motion:
                await self.inu.deactivate(const.Strings.COOLDOWN)
                set_state(self.SensorState.COOLDOWN)

        elif self.state == self.SensorState.COOLDOWN:
            # In cooldown, return to normal after expiry
            if time.time() - self.state_changed > (self.inu.settings.cooldown_time / 1000):
                await self.inu.deactivate()
                set_state(self.SensorState.IDLE)

    async def fire(self):
        self.logger.info(f"Firing; code {self.inu.settings.trigger_code}")
        await self.inu.command(const.Subjects.COMMAND_TRIGGER, {
            'code': self.inu.settings.trigger_code,
        })


if __name__ == "__main__":
    app = MotionApp()
    asyncio.run(app.run())
