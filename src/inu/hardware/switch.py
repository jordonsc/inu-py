from machine import Pin


class SwitchMode:
    NO = "NO"
    NC = "NC"


class PullMode:
    PULL_DOWN = 1
    PULL_UP = 2


class Switch:
    def __init__(self, pin: int, pull: int = PullMode.PULL_DOWN, mode: str = SwitchMode.NO, on_change: callable = None):
        """
        If the `mode` is NC, then an active current on the pin will be considered "off".
        """
        self.pin = Pin(pin, Pin.IN, pull=pull)
        self.state = None
        self.on_change = on_change
        self.reversed = mode == SwitchMode.NC

    async def check_state(self) -> bool:
        """
        Checks the state of the switch input pin. If the state has changed, `on_change(state)` will be called.

        Returns the switch state.
        """
        state = bool(self.pin.value())

        # Reverse the state if we're using a normally-closed circuit
        if self.reversed:
            state = not state

        if state != self.state:
            self.state = state
            if self.on_change:
                await self.on_change(self.state)

        return self.state
