import time

from inu import const
from inu.app import InuApp
from inu.hardware.switch import Switch, SwitchMode


class SwitchManager(InuApp):
    def __init__(self, settings_class: type):
        super().__init__(settings_class)
        self.switches = []
        self.switches_active = 0
        self.activate_on_switch = True
        self.fallback_refire_delay = None

    async def switch_init(self):
        def device_cfg(path, keys, default=None):
            for key in keys:
                if key not in path:
                    return default
                path = path[key]
            return path

        self.fallback_refire_delay = self.get_config(["switch", "refire_delay"], None)

        index = 0
        devices = self.get_config(["switch", "devices"], [])
        for device in devices:
            mode = device_cfg(device, ["mode"], SwitchMode.NO)
            pin = device_cfg(device, ["pin"], None)
            name = device_cfg(device, ["name"], f"s{index}")
            code = device_cfg(device, ["code"], None)
            if not pin:
                self.logger.error("No pin assigned for switch")
                continue

            self.switches.append((Switch(pin=pin, mode=mode), name, code))
            index += 1

    async def switch_tick(self):
        active = 0

        if hasattr(self.inu.settings, "refire_delay"):
            refire_delay = self.inu.settings.refire_delay
        else:
            refire_delay = self.fallback_refire_delay

        for i, (sw, name, code) in enumerate(self.switches):
            # Check each switch for state change
            last_state = sw.state

            # Force all devices to be considered "off" if we've disabled the device
            if self.inu.state.enabled:
                if self.inu.state.locked:
                    # Locked - don't change state (except for disabling)
                    new_state = last_state
                else:
                    new_state = await sw.check_state()
            else:
                new_state = False
                sw.state = False

            if new_state:
                active += 1

                if refire_delay and (sw.get_active_time() >= (refire_delay / 1000)):
                    # Send a re-fire trigger
                    await self.fire_trigger(name, self.get_code_for_switch(i, code))
                    sw.active_time = time.time()

            if last_state != new_state:
                # State changed
                self.logger.info(f"Switch '{name}': {last_state} -> {new_state}")

                if new_state:
                    # If we're moving into an active state, gather the right code and fire -
                    await self.fire_trigger(name, self.get_code_for_switch(i, code))

        if active != self.switches_active:
            # Update the device status if the number of active switches changed
            self.switches_active = active

            if self.activate_on_switch:
                if active > 0:
                    await self.inu.activate(f"Active: {active}")
                else:
                    await self.inu.deactivate()

    def get_code_for_switch(self, index: int, code=None):
        if index > 5:
            # There are only 6 override codes
            code = code or -1
        else:
            if hasattr(self.inu.settings, f"sw_{index}"):
                code = int(getattr(self.inu.settings, f"sw_{index}"))
            else:
                code = code or -1

        # If override code is -1, use the default code (trigger_code)
        if code == -1:
            if hasattr(self.inu.settings, "trigger_code"):
                code = int(self.inu.settings.trigger_code)
            else:
                code = 0

        return code

    async def fire_trigger(self, name, code):
        self.logger.info(f"Switch '{name}' firing; code {code}")
        await self.inu.command(const.Subjects.COMMAND_TRIGGER, {
            'code': code,
        })
