import asyncio

from inu.lib.switch import SwitchManager
from inu.schema.settings.sensors import MultiSwitch


class SwitchApp(SwitchManager):
    def __init__(self):
        super().__init__(MultiSwitch)

    async def app_init(self):
        await self.switch_init()

        s = "" if len(self.switches) == 1 else "s"
        self.logger.info(f"Switch initialised with {len(self.switches)} device{s}")
        await self.set_state_from_last(True)

    async def app_tick(self):
        await self.switch_tick()


if __name__ == "__main__":
    app = SwitchApp()
    asyncio.run(app.run())
