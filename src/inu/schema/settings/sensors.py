from . import Settings, CooldownDevice


class TriggerDevice(Settings, CooldownDevice):
    """
    A device that sends a trigger command.
    """
    trigger_code: int = 0
    trigger_code_hint: str = "`code` to include in the trigger; may correlate to a sequence or special `code`"


class MotionSensor(TriggerDevice):
    """
    ## A motion sensor.
    """
    sensitivity: int = 50
    sensitivity_hint: str = "Sensor trip sensitivity, between 1 (low) and 100 (high)"
    sensitivity_min: int = 1
    sensitivity_max: int = 100


class RangeTrigger(TriggerDevice):
    """
    ## A range-based trip sensor.

    The device will constantly monitor the range of its sensor. If the range drops below `max_distance` the device
    will consider itself "tripped".

    Increase `wait_delay` to reduce sensitivity on false-positives.
    """
    max_distance: int = 1000
    max_distance_hint: str = "If the range drops below this value (in mm), the sensor will trigger"
    max_distance_min: int = 30

    min_distance: int = 0
    min_distance_hint: str = "Range must be above this value (and below max) for a trigger"
    min_distance_min: int = 0

    wait_delay: int = 0
    wait_delay_hint: str = "Time in ms the range must be under the max_distance value before triggering"
    wait_delay_min: int = 0


class MultiSwitch(Settings):
    """
    ## A device with one or more physical switches.

    Override code of -1 uses the default code.
    """
    trigger_code: int = 0
    trigger_code_hint: str = "Default `code` to trigger with, if not set by per-switch overrides"

    refire_delay: int = 0
    refire_delay_hint: str = "Time in ms to send another trigger when sustained (0 to disable)"

    sw_0: int = -1
    sw_0_hint: str = "Switch 0 override code"

    sw_1: int = -1
    sw_1_hint: str = "Switch 1 override code"

    sw_2: int = -1
    sw_2_hint: str = "Switch 2 override code"

    sw_3: int = -1
    sw_3_hint: str = "Switch 3 override code"

    sw_4: int = -1
    sw_4_hint: str = "Switch 4 override code"

    sw_5: int = -1
    sw_5_hint: str = "Switch 5 override code"


class Capacitor(Settings):
    """
    ## A capacitive sensor.
    """
    trigger_code: int = 0
    trigger_code_hint: str = "Default `code` to trigger with, if not set by per-switch overrides"

    sensor_low: int = 25000
    sensor_low_hint: str = "Raw low value for 0% threshold"

    sensor_high: int = 50000
    sensor_high_hint: str = "Raw high value for 100% threshold"

    trigger_on: int = 50
    trigger_on_hint: str = "Value as a percentage, to be above or below to activate trigger"

    trigger_off: int = 60
    trigger_off_hint: str = "Value as a percentage, to be above or below to deactivate trigger"

    refire_delay: int = 0
    refire_delay_hint: str = "Time in ms to send another trigger when sustained (0 to disable)"

    delay_wait: int = 0
    delay_wait_hint: str = "Time in ms to wait before triggering at threshold"


class LightSensor(Settings):
    """
    ## An ambient light sensor.
    """
    trigger_code: int = 0
    trigger_code_hint: str = "Default `code` to trigger with, if not set by per-switch overrides"

    trigger_on: int = 5
    trigger_on_hint: str = "Value in lux, to be above or below to activate trigger"

    trigger_off: int = 15
    trigger_off_hint: str = "Value in lux, to be above or below to deactivate trigger"

    refire_delay: int = 0
    refire_delay_hint: str = "Time in ms to send another trigger when sustained (0 to disable)"

    delay_wait: int = 0
    delay_wait_hint: str = "Time in ms to wait before triggering at threshold"
