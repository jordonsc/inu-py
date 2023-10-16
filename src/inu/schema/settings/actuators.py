from . import Settings, CooldownDevice


class Actuator(Settings, CooldownDevice):
    """
    ## A physical actuator, driving a mechanical action.
    """
    actuator_speed: int = 50
    actuator_speed_hint: str = "Speed of the motor or actuator as a percentage (1 to 100)"
    actuator_speed_min: int = 1
    actuator_speed_max: int = 100


class Door(Actuator):
    """
    ## Door open/close motorised controller.

    The door will open for `drive_ticks` and then wait for `wait_time` before reversing the motion.
    """
    drive_ticks: int = 5000
    drive_ticks_hint: str = "Number of \"ticks\" to drive the device"
    drive_ticks_min: int = 100

    wait_time: int = 0
    wait_time_hint: str = "Time in ms to wait before reversing the action."
    wait_time_min: int = 0

    auto_calibrate: bool = True
    auto_calibrate_hint = "Intelligently reset the devices position after execution"
