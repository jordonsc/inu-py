import asyncio
import logging

from . import Control
from ..robotics import RoboticsDevice, Move
from machine import Pin, PWM
import time

from ..switch import Switch


class StepperDriver:
    def __init__(self, pulse, direction, enabled):
        self.pulse = Pin(pulse, Pin.OUT)
        self.direction = Pin(direction, Pin.OUT)
        self.enabled = Pin(enabled, Pin.OUT)


class Screw:
    def __init__(self, steps_per_rev: int = 1600, screw_lead: int = 8, forward: int = 1):
        # Number of steps per revolution
        self.steps_per_rev = steps_per_rev

        # Screw lead (distance actuator moves for 1 rotation)
        self.screw_lead = screw_lead

        # Driver direction that is "forward"
        self.forward = forward

    def __repr__(self):
        return f"steps/rev: {self.steps_per_rev}; lead: {self.screw_lead}"


class Actuator(RoboticsDevice):
    """
    Moves an actuator forward or backwards.

    Supports undoing partial operations on interrupt.
    """

    CONFIG_CODE = "stepper"

    # Required time remaining in an operation (in nanoseconds) to allow yielding CPU
    MIN_SLEEP_TIME = 0.25 * 10 ** 9  # 0.25 seconds

    # Time to pause when interrupted before reversing
    INT_PAUSE_TIME = 0.5

    def __init__(self, driver: StepperDriver, screw: Screw, safe_wait: int = 250, fwd_stop: Switch = None,
                 rev_stop: Switch = None, allow_sleep: bool = True):
        """
        `allow_sleep` will allow the device to yield CPU if there is more than MIN_SLEEP_TIME nanoseconds remaining in
        the operation.
        """
        super().__init__()
        self.logger = logging.getLogger("inu.robotics.actuator")

        self.driver = driver
        self.screw = screw

        self.driver.pulse.off()
        self.driver.direction.off()
        self.driver.enabled.off()

        # It is important to delay a small amount in order to allow a clean finish to the PWM signal after stopping the
        # stepper. If you don't do this, and start another PWM signal immediately, it might cause the driver to
        # overload. The higher the steps/rev, the lower this value can be.
        self.safe_wait_time = safe_wait

        self.fwd_stop = fwd_stop
        self.rev_stop = rev_stop

        self.allow_sleep = allow_sleep

        # Displacement of last operation
        self.displacement = 0

    def on(self):
        """
        Power the stepper motor preventing rotation while idle.
        """
        self.set_power(True)

    def off(self):
        """
        Un-power the stepper motion, allowing rotation while idle.
        """
        self.set_power(False)

    def set_power(self, on: bool):
        """
        Set the 'enable' option on the stepper driver. If set to True, the motor will not allow rotation while not in
        use. If disabled, the motor will be permitted rotation while not active.

        NB: Calling `drive()` will enable the motor power, but not disable it following.
        """
        self.driver.enabled.value(on)

    def distance_to_steps(self, displacement: float) -> int:
        """
        Calculate the number of stepper motor steps for the given actuator displacement in mm.
        """
        return round((displacement / self.screw.screw_lead) * self.screw.steps_per_rev)

    def pulse_rate_from_speed(self, speed: float) -> int:
        """
        Calculate the pulses per second from a speed.
        """
        return round(speed / self.screw.screw_lead * self.screw.steps_per_rev)

    async def drive(self, distance: float, speed: float = 10, direction: int = 1, ignore_int=False):
        """
        Move the actuator by a given distance.

        distance:  distance to move the actuator in mm
        speed:     speed to move the actuator in mm/s
        direction: direction of stepper motor, 1 == "forward"

        CAUTION: do not drive immediately after a high-speed drive, or change rotation back-to-back.
                 a delay of 0.2s is recommended.

        If the driver isn't enabled, it will be enabled. Does not disable upon completion.
        """
        fwd = direction == 1

        # Flip the direction if the screw direction is reversed
        direction = int(not (self.screw.forward ^ direction))

        if self.driver.enabled.value() == 0:
            self.set_power(True)

        if self.driver.direction.value() != direction:
            self.driver.direction.value(direction)

        pps = self.pulse_rate_from_speed(speed)
        op_time = distance / speed * 10 ** 9
        self.displacement = 0
        self.logger.info(f"Op time: {op_time * 10 ** -9}")
        self.logger.info(f"Safe wait: {self.safe_wait_time / 1000}")

        # Don't even start the stepper if the limiter is already triggered
        if fwd and self.fwd_stop and await self.fwd_stop.check_state():
            return

        if not fwd and self.rev_stop and await self.rev_stop.check_state():
            return

        start_time = time.time_ns()
        pwm = PWM(self.driver.pulse, freq=pps, duty=512)

        # Do NOT use sleep when we're close to reaching `op_time` - this must be as dead accurate as possible
        while True:
            run_time = time.time_ns() - start_time
            rem_time = op_time - run_time

            # Operation completed
            if run_time >= op_time:
                break

            # An interrupt signal has been received, we need to stop and reverse the action
            if not ignore_int and self.interrupted:
                # We'll exit cleanly and the caller can deal with the reverse op
                self.logger.info("Interrupted")
                break

            # If we have sufficient time, we'll check the GPIO pins for the end-stops
            if fwd and self.fwd_stop and await self.fwd_stop.check_state():
                break
            if not fwd and self.rev_stop and await self.rev_stop.check_state():
                break

            # We'll only allow a sleep if we have a safe amount of time remaining before cut-off
            if self.allow_sleep and rem_time > self.MIN_SLEEP_TIME:
                # Allow other tasks to run if we have more than MIN_SLEEP_TIME ns remaining
                await asyncio.sleep(0)

        pwm.deinit()
        self.displacement = (run_time * speed) / (10 ** 9)
        print("safe wait")
        await asyncio.sleep(self.safe_wait_time / 1000)

    async def execute(self, ctrl: Control, reverse: bool = False):
        await super().execute(ctrl)

        if isinstance(ctrl, Move):
            if reverse:
                direction = int(ctrl.get_distance() < 0)
            else:
                direction = int(ctrl.get_distance() >= 0)

            distance = abs(ctrl.get_distance())
            await self.drive(distance, ctrl.get_speed(), direction, ignore_int=reverse)

            if not reverse and self.interrupted:
                await asyncio.sleep(self.INT_PAUSE_TIME)
                self.logger.info(f"Interrupt reverse for {self.displacement} mm")
                await self.drive(self.displacement, ctrl.get_speed(), int(not bool(direction)), ignore_int=True)

    def __repr__(self):
        return f"Stepper <{self.screw}>"
