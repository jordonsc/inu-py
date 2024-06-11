from inu import error


class Control:
    """
    Controls represent actions that can be taken and are constructed from a control string. eg:
        SEL A0; MV 800 300; W 2000 INT; MV -800 150 INT
        SEL L0:0: COL 255 0 0; SEL L0:1; COL 0 0 255!
    """
    INTERRUPT_CODE = "INT"
    EXECUTE_CODE = "!"
    DELIMITER = ";"

    def __init__(self, cmd: str):
        # Allow the current operation to be interrupted by an INT signal
        self.allow_int = False
        # Instruct the operation to commit/write/execute - required for light changes, etc.
        self.execute = False
        # The control code
        self.code = None
        # Arguments for the control code
        self.args = []

        if cmd is not None:
            self._parse(cmd)

    def allow_interrupt(self) -> bool:
        """
        Check if this control allowed interruption.
        """
        return self.allow_int

    def _parse(self, cmd: str):
        """
        Breaks down `cmd` into args, separating special operators.
        """
        args = cmd.strip().upper().split(" ")
        if len(args) < 2:
            raise error.Malformed(f"Invalid control string: {cmd}")

        self.code = args.pop(0)

        while len(args):
            arg = args.pop(0)
            if arg == self.INTERRUPT_CODE:
                self.allow_int = True
            elif arg == self.EXECUTE_CODE:
                self.execute = True
            else:
                self.args.append(arg)

        if len(self.args) < 1:
            raise error.Malformed(f"No control arguments: {cmd}")
