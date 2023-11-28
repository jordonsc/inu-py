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


class OpVector:
    def __init__(self, min_speed, speed, distance, ramp_accel):
        self.min_speed = min_speed
        self.speed = speed
        self.total_displacement = distance
        self.ramp_accel = max(self.get_min_ramp_accel(), ramp_accel)

        # Time spent ramping up/down
        self.ramp_time = speed / self.ramp_accel
        # Displacement during a single ramp phase
        self.ramp_displacement = ((speed - min_speed) + min_speed) / 2 * self.ramp_time
        # Displacement during the full-speed phase
        self.full_displacement = distance - (self.ramp_displacement * 2)

        self.ramp_time = self.ramp_time * 10 ** 9  # convert to NS
        self.full_spd_time = self.full_displacement / speed * 10 ** 9
        self.op_time = self.full_spd_time + (self.ramp_time * 2)

    def get_min_ramp_accel(self):
        """
        Returns the minimum acceleration we need to ramp at in order to hit full-speed during the operation.
        """
        return (2 * self.speed ** 2) / self.total_displacement

    def __repr__(self):
        return f"<op ramp_in={round(self.ramp_time * 10 ** -9, 2)} " + \
               f"full_spd={round(self.full_spd_time * 10 ** -9, 2)} " + \
               f"ramp_out={round(self.ramp_time * 10 ** -9, 2)} " + \
               f"op_time={round(self.op_time * 10 ** -9, 2)}>"


class Actuator(RoboticsDevice):
    """
    Moves an actuator forward or backwards.

    Supports undoing partial operations on interrupt.
    """
    CONFIG_ALIASES = ["actuator", "stepper"]

    # Required time remaining in an operation (in nanoseconds) to allow yielding CPU
    MIN_SLEEP_TIME = 0.25 * 10 ** 9  # 0.25 seconds

    # Time to pause when interrupted before reversing
    INT_PAUSE_TIME = 0.5

    class DisplacementPhase:
        RAMP_UP = 0
        FULL_SPEED = 1
        RAMP_DOWN = 2
        END = 3

    def __init__(self, driver: StepperDriver, screw: Screw, safe_wait: int = 50, ramp_speed: int = 250,
                 fwd_stop: Switch = None, rev_stop: Switch = None, allow_sleep: bool = True):
        """
        `safe_wait` is a delay in ms to hold after stopping the stepper.
        `ramp_speed` is the acceleration rate in mm/s to start/stop the stepper.
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
        self.ramp_accel = ramp_speed

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

        # Don't even start the stepper if the limiter is already triggered
        if fwd and self.fwd_stop and await self.fwd_stop.check_state():
            return

        if not fwd and self.rev_stop and await self.rev_stop.check_state():
            return

        # Calculate ramp times
        op = OpVector(min_speed=10, speed=speed, distance=distance, ramp_accel=self.ramp_accel)
        self.logger.info(op)

        self.displacement = 0
        phase = self.DisplacementPhase.RAMP_UP
        run_time = 0
        current_speed = op.min_speed

        last_tick = time.time_ns()
        start_time = last_tick

        pwm = PWM(self.driver.pulse, freq=self.pulse_rate_from_speed(current_speed), duty=512)

        while True:
            if self.displacement >= distance:
                break

            # An interrupt signal has been received, we need to stop and reverse the action
            if not ignore_int and self.interrupted:
                # We'll exit cleanly and the caller can deal with the reverse op
                if phase == self.DisplacementPhase.END:
                    break
                elif phase < self.DisplacementPhase.RAMP_DOWN:
                    self.logger.info("Interrupted")
                    phase = self.DisplacementPhase.RAMP_DOWN

            # Check limiters
            if fwd and self.fwd_stop and await self.fwd_stop.check_state():
                break
            if not fwd and self.rev_stop and await self.rev_stop.check_state():
                break

            tick = time.time_ns()
            tick_time = tick - last_tick
            if tick_time == 0:
                continue
            else:
                last_tick = tick

            self.displacement += current_speed * tick_time * 10 ** -9
            run_time = tick - start_time

            # Update PWM speed/phase
            if phase == self.DisplacementPhase.RAMP_UP:
                pos = run_time / op.ramp_time
                current_speed = min(((op.speed - op.min_speed) * pos) + op.min_speed, op.speed)
                pwm.freq(self.pulse_rate_from_speed(current_speed))
                if current_speed >= op.speed:
                    self.logger.info(f"Move to full-speed phase at {run_time * 10 ** -9} s; pos {pos}")
                    phase = self.DisplacementPhase.FULL_SPEED
            elif phase == self.DisplacementPhase.FULL_SPEED:
                if run_time >= op.ramp_time + op.full_spd_time:
                    self.logger.info(f"Move to ramp-down phase at {run_time * 10 ** -9} s")
                    phase = self.DisplacementPhase.RAMP_DOWN
            elif phase == self.DisplacementPhase.RAMP_DOWN:
                pos = 1 - ((run_time - op.full_spd_time - op.ramp_time) / op.ramp_time)
                current_speed = max(((op.speed - op.min_speed) * pos) + op.min_speed, op.min_speed)
                pwm.freq(self.pulse_rate_from_speed(current_speed))
                if current_speed <= op.min_speed:
                    self.logger.info(f"Move to end phase at {run_time * 10 ** -9} s; pos {pos}")
                    phase = self.DisplacementPhase.END

                    # if we've been interrupted, exit immediately - don't attempt to finish the full distance
                    if not ignore_int and self.interrupted:
                        break

            # Ramp-down/end is time-sensitive, do not allow sleeping (passing CPU to other tasks)
            if phase < self.DisplacementPhase.RAMP_DOWN:
                await asyncio.sleep(0)

        pwm.deinit()
        await asyncio.sleep(self.safe_wait_time / 1000)

        self.logger.info(f"Done in {run_time * 10 ** -9} s; displacement: {self.displacement}")

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
