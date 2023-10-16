from . import Settings, CooldownDevice


class MotionSensor(Settings, CooldownDevice):
    """
    ## A motion sensor.
    """
    sensitivity: int = 50
    sensitivity_hint: str = "Sensor trip sensitivity, between 1 (low) and 100 (high)"
    sensitivity_min: int = 1
    sensitivity_max: int = 100


class RangeTrigger(Settings, CooldownDevice):
    """
    ## A range-based trip sensor.

    The device will constantly monitor the range of its sensor. If the range drops below `max_distance` the device
    will consider itself "tripped".

    Increase `wait_delay` to reduce sensitivity on false-positives.
    """
    max_distance: int = 1000
    max_distance_hint: str = "If the range drops below this value (in mm), the sensor will trigger"
    max_distance_min: int = 30

    wait_delay: int = 0
    wait_delay_hint: str = "Time in ms the range must be under the max_distance value before triggering"
    wait_delay_min: int = 0
