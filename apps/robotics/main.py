import asyncio

from inu.app import InuApp
from inu.hardware import stepper
from inu.schema.settings.robotics import Robotics
from micro_nats.util.asynchronous import TaskPool


class RoboticsApp(InuApp):
    def __init__(self):
        super().__init__(Robotics)
        self.pool = TaskPool()
        self.stepper = stepper.Stepper(
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
        )

    async def main_loop(self):
        """
        Endless app loop.
        """
        await self.init()
        self.logger.info(f"Lead screw: {self.stepper.screw}")

        while True:
            await self.on_loop()
            await asyncio.sleep(0.01)


if __name__ == "__main__":
    app = RoboticsApp()
    asyncio.run(app.main_loop())
