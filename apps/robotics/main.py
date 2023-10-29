import asyncio

from inu import error
from inu.app import InuApp
from inu.const import LogLevel
from inu.hardware.robotics import Robotics, stepper
from inu.schema.settings.robotics import Robotics as RoboSettings
from micro_nats.util.asynchronous import TaskPool


class RoboticsApp(InuApp):
    def __init__(self):
        super().__init__(RoboSettings)
        self.pool = TaskPool()
        self.robotics = Robotics()

    def load_devices(self):
        """
        Read device configuration and bootstrap the robotics controller with device information.
        """
        devices = self.get_config(["robotics", "devices"])
        if not isinstance(devices, dict):
            raise error.Malformed(f"Malformed device configuration for robotics")

        def device_cfg(path, keys, default=None):
            for key in keys:
                if key not in path:
                    return default
                path = path[key]
            return path

        for device_id, spec in devices.items():
            device_type = device_cfg(spec, ["type"])
            if device_type == stepper.Stepper.CONFIG_CODE:
                self.robotics.add_device(device_id, stepper.Stepper(
                    stepper.StepperDriver(
                        pulse=self.get_config(["robotics", "driver", "pulse_pin"], 33),
                        direction=self.get_config(["robotics", "driver", "direction_pin"], 38),
                        enabled=self.get_config(["robotics", "driver", "enabled_pin"], 8),
                    ),
                    stepper.LeadScrew(
                        steps_per_rev=self.get_config(["robotics", "screw", "steps_per_rev"], 1600),
                        microstepping=self.get_config(["robotics", "screw", "microstepping"], 8),
                        screw_lead=self.get_config(["robotics", "screw", "screw_lead"], 5),
                    ),
                ))

    async def app_init(self):
        self.load_devices()

        s = "" if len(self.robotics.devices) == 1 else "s"
        await self.inu.log(f"Robotics initialised with {len(self.robotics.devices)} device{s}")

        self.inu.status(enabled=True)

    async def app_tick(self):
        pass

    async def on_trigger(self, code: int):
        # Actionable sequence codes range from seq_0 to seq_5
        if 0 <= code <= 5:
            seq = f"seq_{code}"
            ctrl = getattr(self.inu.settings, seq).strip()

            if len(ctrl) == 0:
                await self.inu.log(f"Ignoring sequence {code} with no control codes")
                return

            await self.inu.log(f"Execute sequence {code} // {ctrl}")
            try:
                await self.inu.activate(f"Sequence {code}")
                # robotics may refuse CPU, so sleep enough time to dispatch the status update
                await asyncio.sleep(0.05)
                await self.robotics.run(ctrl)
                await self.inu.deactivate()
            except Exception as e:
                await self.inu.log(f"Exception in robotics execution - {type(e).__name__}: {e}", LogLevel.ERROR)


if __name__ == "__main__":
    app = RoboticsApp()
    asyncio.run(app.run())
