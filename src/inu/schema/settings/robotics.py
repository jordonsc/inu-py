from . import Settings, CooldownDevice, ActionDevice


class Robotics(Settings, ActionDevice, CooldownDevice):
    """
    ## A collection of 1 or more actuators, steppers or servos that control a robotic action.

    Control codes:
     Ax[:y]  select actuator x [and set speed to y mm/m]
     Sx[:y]  select server x
     Mx[:y]  select motor x
     Mx      move x mm
     Wx      wait x milliseconds

    Example:
        A0:5000; M500; W2000; M-500

        Selects 'actuator 0', and sets speed to 5000 mm/m
        Move (actuator 0) 500 mm
        Wait 2 seconds
        Move in reverse direction 500 mm (to original state)
    """
    seq_0: str = "A0:5000; M500; W2000; M-500"
    seq_0_hint: str = "Sequence 0 control codes"

    seq_1: str = ""
    seq_1_hint: str = "Sequence 1 control codes"

    seq_2: str = ""
    seq_2_hint: str = "Sequence 2 control codes"

    seq_3: str = ""
    seq_3_hint: str = "Sequence 3 control codes"

    seq_4: str = ""
    seq_4_hint: str = "Sequence 4 control codes"

    seq_5: str = ""
    seq_5_hint: str = "Sequence 5 control codes"
