import asyncio
import time

from inu import const
from inu.app import InuApp
from inu.hardware.switch import Switch, SwitchMode
from inu.schema.settings.sensors import MultiSwitch
from micro_nats.util.asynchronous import TaskPool


class SwitchApp(InuApp):
    def __init__(self):
        super().__init__(MultiSwitch)
        self.pool = TaskPool()
        self.devices = []
        self.active: int = 0

    async def app_init(self):
        def device_cfg(path, keys, default=None):
            for key in keys:
                if key not in path:
                    return default
                path = path[key]
            return path

        devices = self.get_config(["switch", "devices"], [])
        for device in devices:
            mode = device_cfg(device, ["mode"], SwitchMode.NO)
            pin = device_cfg(device, ["pin"], None)
            if not pin:
                self.logger.error("No pin assigned for switch")
                continue

            self.devices.append(Switch(pin=pin, mode=mode))

        s = "" if len(self.devices) == 1 else "s"
        self.logger.info(f"Switch initialised with {len(self.devices)} device{s}")
        await self.set_state_from_last(True)

    async def app_tick(self):
        active = 0
        for i, sw in enumerate(self.devices):
            # Check each switch for state change
            last_state = sw.state

            # Force all devices to be considered "off" if we've disabled the device
            if self.inu.state.enabled:
                new_state = await sw.check_state()
            else:
                new_state = False
                sw.state = False

            if new_state:
                active += 1

                if self.inu.settings.refire_delay and (sw.get_active_time() >= (self.inu.settings.refire_delay / 1000)):
                    # Send a re-fire trigger
                    await self.fire(i, self.get_code_for_switch(i))
                    sw.active_time = time.time()

            if last_state != new_state:
                # State changed
                self.logger.info(f"Switch {i}: {last_state} -> {new_state}")

                if new_state:
                    # If we're moving into an active state, gather the right code and fire -
                    await self.fire(i, self.get_code_for_switch(i))

        if active != self.active:
            # Update the device status if the number of active switches changed
            self.active = active

            if active > 0:
                await self.inu.activate(f"Active: {active}")
            else:
                await self.inu.deactivate()

    def get_code_for_switch(self, index: int):
        if index > 5:
            # There are only 6 override codes
            code = -1
        else:
            code = int(getattr(self.inu.settings, f"sw_{index}"))

        # If override code is -1, use the default code (trigger_code)
        if code == -1:
            code = int(self.inu.settings.trigger_code)

        return code

    async def fire(self, index, code):
        self.logger.info(f"Switch {index} firing; code {code}")
        await self.inu.command(const.Subjects.COMMAND_TRIGGER, {
            'code': code,
        })


if __name__ == "__main__":
    app = SwitchApp()
    asyncio.run(app.run())
