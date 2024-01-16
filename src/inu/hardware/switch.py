import time

from machine import Pin


class SwitchMode:
    NO = "NO"
    NC = "NC"


class PullMode:
    PULL_DOWN = 1
    PULL_UP = 2


class Switch:
    def __init__(self, pin: int, pull: int = PullMode.PULL_DOWN, mode: str = SwitchMode.NO, min_active: int = 0,
                 on_change: callable = None):
        """
        If the `mode` is NC, then an active current on the pin will be considered "off".
        If `min_active` is set to non-zero, then the hardware must be in a new state for `min_active` ms before
        changing state.
        """
        self.pin = Pin(pin, Pin.IN, pull=pull)
        self.state = None
        self.on_change = on_change
        self.reversed = mode == SwitchMode.NC
        self.min_active = min_active

        # Time the hardware changed state, we'll time until `min_active` ms then trigger a change
        self.begin_state_change = None

        # Time the device has been in an active state
        self.active_time = None

    async def check_state(self, no_delay=False) -> bool:
        """
        Checks the state of the switch input pin. If the state has changed, `on_change(state)` will be called.

        Returns the switch state.
        """
        state = bool(self.pin.value())

        # Reverse the state if we're using a normally-closed circuit
        if self.reversed:
            state = not state

        if state != self.state:
            if not no_delay and self.min_active > 0:
                # We require a delay before changing state
                if self.begin_state_change is None:
                    self.begin_state_change = time.time()
                    return self.state
                else:
                    if time.time() - self.begin_state_change < (self.min_active / 1000):
                        return self.state

            # State has changed, start an active time and trigger callbacks
            self.state = state

            if state:
                self.active_time = time.time()
            else:
                self.active_time = None

            if self.on_change:
                await self.on_change(self.state)

        else:
            # State is the same, check if we should reset the state-change counter
            if self.begin_state_change is not None:
                # This will happen if the device physically changes state quickly in succession before the min active
                # time has expired (eg filter interference)
                self.begin_state_change = None

        return self.state

    def get_active_time(self):
        """
        Returns the time the device has been active for, in seconds.
        """
        if not self.active_time:
            return 0

        return time.time() - self.active_time
