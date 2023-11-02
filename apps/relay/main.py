import asyncio
import time

from inu.app import InuApp
from inu.hardware.relay import Relay
from inu.schema.settings import Relay as RelaySettings
from micro_nats.util.asynchronous import TaskPool


class RelayApp(InuApp):
    def __init__(self):
        super().__init__(RelaySettings)
        self.pool = TaskPool()

        self.trigger_start = None
        self.relay = Relay(
            pin=self.get_config(["relay", "pin"], 33),
            ground=self.get_config(["relay", "ground"], None),
            on_state_change=self.on_state_change
        )

        self.relay.off()

    async def app_init(self):
        await self.inu.status(enabled=True, active=False, status="")

    async def app_tick(self):
        if self.trigger_start is not None and (
                time.time() - self.trigger_start >= self.inu.settings.time_delay
        ):
            # Time delay expired, disable relay and clear timer
            self.trigger_start = None
            await self.relay.off()

    async def on_trigger(self, code: int):
        if code == 1:
            # Turn the relay on, disable any timers
            self.trigger_start = None
            await self.relay.on()
        elif code == 2:
            # Turn the relay off, disable any timers
            self.trigger_start = None
            await self.relay.off()
        elif code == 0:
            if self.inu.settings.time_delay == 0:
                # Toggle the relay (timers should not be in use)
                self.trigger_start = None
                await self.relay.toggle()
            else:
                # Activate the relay and start the delay timer
                self.trigger_start = time.time()
                await self.relay.on()
        else:
            self.logger.warning(f"Ignoring trigger with code {code}")

    async def on_state_change(self, active: bool):
        await self.inu.status(enabled=True, active=active, status='ON' if active else 'OFF')


if __name__ == "__main__":
    app = RelayApp()
    asyncio.run(app.run())
