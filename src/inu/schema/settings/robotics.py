from . import Settings, CooldownDevice, ActionDevice


class Robotics(Settings, ActionDevice, CooldownDevice):
    """
    ## A collection of 1 or more actuators, steppers or servos that control a robotic action.

    **Control Codes**
        ```
        SEL <DEVICE ID>               Select a device
        MV <DISTANCE> <SPEED> [INT]   Move DISTANCE mm, at speed of SPEED mm/s
        W <TIME> [INT]                Pause for TIME milliseconds
        ```

    If "INT" is appended to the command, it will allow an interrupt trigger (code 100) to reset the operation. INT
    operations may be chained, the full chain will be reversed and eventually replayed.

    Example:
        SEL A0; MV 800 300; W 2000 INT; MV -800 150 INT

        Selects device "A0"
        Move actuator 800 mm at 300 mm/s
        Wait 2 seconds
        Move in reverse direction 800 mm at 150 mm/s
    """
    seq_0: str = "SEL A0; MV 800 300; W 2000; MV -800 150"
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
