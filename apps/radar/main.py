import asyncio

from inu import const
from inu.app import InuApp
from inu.hardware.mmwave.mr24hpc1 import Mr24hpc1
from inu.schema.settings.sensors import RadarSensor
from micro_nats.util.asynchronous import TaskPool


class RadarApp(InuApp):
    TYPE_MR24HPC1 = "mr24hpc1"

    def __init__(self):
        super().__init__(RadarSensor)
        self.pool = TaskPool()
        self.motion_type = self.get_config(["radar", "type"], self.TYPE_MR24HPC1)

        if self.motion_type == self.TYPE_MR24HPC1:
            self.sensor = Mr24hpc1()
        else:
            raise NotImplemented(f"Radar sensor type '{self.motion_type}' not supported")

        self.is_active = False
        self.state = None

    async def app_init(self):
        self.pool.run(self.sensor.read_loop())
        await self.set_state_from_last(True)
        await self.set_sensor_calibration()

    async def update_state(self):
        was_active = self.is_active
        self.is_active = self.sensor.radar.is_present()
        self.state = str(self.sensor.radar)
        await self.inu.status(active=self.sensor.radar.is_moving() is not None, status=self.state)

        if not was_active and self.sensor.radar.is_present():
            # ensure you fire a trigger _after_ updating the state
            await self.fire()

    async def app_tick(self):
        new_state = str(self.sensor.radar)

        if new_state != self.state:
            await self.update_state()

    async def fire(self):
        self.logger.info(f"Firing; code {self.inu.settings.trigger_code}")
        await self.inu.command(const.Subjects.COMMAND_TRIGGER, {
            'code': self.inu.settings.trigger_code,
        })

    async def on_trigger(self, code: int):
        """
        Called when a listen-device publishes a `trigger` message.
        """
        pass

    async def on_settings_updated(self):
        await super().on_settings_updated()
        await self.set_sensor_calibration()

    async def set_sensor_calibration(self):
        # Calibrate sensor
        template = self.inu.settings.template
        cfg = self.get_config(["radar", "templates", template], None)

        if cfg is None:
            self.inu.log(f"Radar template '{template}' not in device configuration", level="error")
            return

        self.logger.info(f"Calibrating radar sensor with template '{template}'")
        await self.sensor.calibrate(cfg)


if __name__ == "__main__":
    app = RadarApp()
    asyncio.run(app.run())
