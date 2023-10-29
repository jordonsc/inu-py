from . import Control
from ..robotics import RoboticsDevice, Move
from machine import Pin, PWM
import time


class StepperDriver:
    def __init__(self, pulse, direction, enabled):
        self.pulse = Pin(pulse, Pin.OUT)
        self.direction = Pin(direction, Pin.OUT)
        self.enabled = Pin(enabled, Pin.OUT)


class LeadScrew:
    def __init__(self, steps_per_rev: int = 1600, microstepping: int = 8, screw_lead: int = 8, forward: int = 1):
        # Number of steps per revolution
        self.steps_per_rev = steps_per_rev

        # Number of microsteps in a step
        self.microsteps = microstepping

        # Screw lead (distance actuator moves for 1 rotation)
        self.screw_lead = screw_lead

        # Driver direction that is "forward"
        self.forward = forward

    def __repr__(self):
        return f"steps/rev: {self.steps_per_rev}; microsteps: {self.microsteps}; lead: {self.screw_lead}"


class Stepper(RoboticsDevice):
    CONFIG_CODE = "stepper"

    def __init__(self, driver: StepperDriver, screw: LeadScrew):
        self.driver = driver
        self.screw = screw

        self.driver.pulse.off()
        self.driver.direction.off()
        self.driver.enabled.off()

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

    async def drive(self, distance: float, speed: float = 10, direction: int = 1):
        """
        Move the actuator by a given distance.

        distance:  distance to move the actuator in mm
        speed:     speed to move the actuator in mm/s
        direction: direction of stepper motor

        CAUTION: do not drive immediately after a high-speed drive, or change rotation back-to-back.
                 a delay of 0.2s is recommended.

        If the driver isn't enabled, it will be enabled. Does not disable upon completion.
        """
        # Flip the direction if the screw direction is reversed
        direction = int(not (self.screw.forward ^ direction))

        if self.driver.enabled.value() == 0:
            self.set_power(True)

        if self.driver.direction.value() != direction:
            self.driver.direction.value(direction)

        pps = self.pulse_rate_from_speed(speed)
        op_time = distance / speed * 10 ** 9

        start_time = time.time_ns()
        pwm = PWM(self.driver.pulse, freq=pps, duty=512)

        # Do NOT use sleep - this must be as dead accurate as possible
        while time.time_ns() - start_time < op_time:
            pass

        pwm.deinit()

    async def execute(self, ctrl: Control):
        if isinstance(ctrl, Move):
            direction = int(ctrl.get_distance() >= 0)
            distance = abs(ctrl.get_distance())
            await self.drive(distance, ctrl.get_speed(), direction)

    def __repr__(self):
        return f"Stepper <{self.screw}>"
