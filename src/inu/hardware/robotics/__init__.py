import asyncio
import logging

from ... import error


class Control:
    """
    Controls represent actions that can be taken and are constructed from a control string. eg:
        SEL A0; MV 800 300; W 2000 INT; MV -800 150 INT
    """
    INTERRUPT_CODE = "INT"
    DELIMITER = ";"

    def __init__(self, cmd: str):
        self.allow_int = False
        self.code = None
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
            else:
                self.args.append(arg)

        if len(self.args) < 1:
            raise error.Malformed(f"No control arguments: {cmd}")


class Select(Control):
    """
    Select the active device. Should precede execution controls like MV.
    """
    CONTROL_CODE = "SEL"
    ALIASES = ["SEL", "S", "SELECT"]

    def __init__(self, ctrl: str = None):
        super().__init__(ctrl)

        if self.code not in self.ALIASES or len(self.args) != 1:
            raise error.Malformed(f"Invalid {self.CONTROL_CODE} control: {ctrl}")

    def get_device(self) -> str:
        """
        Returns the selection subject.
        """
        return self.args[0]

    def __repr__(self):
        return f"SEL {self.get_device()}"


class Wait(Control):
    """
    Delay by a given time in milliseconds.
    """
    CONTROL_CODE = "WAIT"
    ALIASES = ["W", "WAIT"]

    def __init__(self, ctrl: str = None):
        super().__init__(ctrl)

        if self.code not in self.ALIASES or len(self.args) != 1:
            raise error.Malformed(f"Invalid {self.CONTROL_CODE} control: {ctrl}")

    def get_time(self) -> int:
        """
        Wait time as an integer in milliseconds.
        """
        return int(self.args[0])

    def __repr__(self):
        return f"WAIT {self.get_time()}"


class Move(Control):
    """
    Move the device, such as an actuator, by a given distance at a given speed.
    """
    CONTROL_CODE = "MV"
    ALIASES = ["M", "MV", "MOVE"]

    def __init__(self, ctrl: str = None):
        super().__init__(ctrl)

        if self.code not in self.ALIASES or len(self.args) != 2:
            raise error.Malformed(f"Invalid {self.CONTROL_CODE} control: {ctrl}")

    def get_distance(self) -> int:
        """
        Distance of the move operation, in mm.
        """
        return int(self.args[0])

    def get_speed(self) -> int:
        """
        Speed to move the actuator in mm/s.
        """
        return int(self.args[1])

    def __repr__(self):
        return f"MV {self.get_distance()} mm @ {self.get_speed()} mm/s"


CONTROL_MAP = {
    """
    Mapping from string codes into control classes.
    """

    "S": Select,
    "SEL": Select,
    "SELECT": Select,
    "W": Wait,
    "WAIT": Wait,
    "M": Move,
    "MV": Move,
    "MOVE": Move,
}


class RoboticsDevice:
    """
    Base class for a physical device controller. Must be able to execute Control actions.
    """

    async def execute(self, ctrl: Control):
        """
        Run a control code. Non-tangible controls like SEL and WAIT will not be sent to a RoboticsDevice.
        """
        pass

    def set_power(self, powered: bool):
        """
        Powers or un-powers the device. May do nothing depending on if the device has a passive power state.
        """
        pass


class Robotics:
    """
    Robotics manager service.
    """

    def __init__(self):
        self.devices = {}
        self.active_device = None
        self.logger = logging.getLogger("inu.robotics")

    def add_device(self, device_id: str, controller: RoboticsDevice):
        """
        Add a RoboticsDevice controller to the list of actionable devices.
        """
        self.logger.info(f"Adding controller: {controller}")
        self.devices[device_id] = controller

    def select_device(self, device: Select):
        """
        Execute a SEL control code.
        """
        if device.get_device() not in self.devices:
            raise error.BadRequest(f"Device '{device.get_device()}' not registered")

        self.active_device = device.get_device()

    def set_power(self, powered: bool):
        """
        Modifies the power state for all devices.
        """
        for device in self.devices:
            device.set_power(powered)

    async def run(self, ctrl_list: str):
        """
        Run a control code string.
        """
        control_list = self.control_array_from_string(ctrl_list)

        for ctrl in control_list:
            self.logger.info(f"EXEC: {ctrl}")

            # Non-tangible codes -
            if isinstance(ctrl, Select):
                self.select_device(ctrl)
            elif isinstance(ctrl, Wait):
                await asyncio.sleep(ctrl.get_time() / 1000)
            elif ctrl is None:
                self.logger.warning("Null control code provided")
            else:
                # Tangible codes need to be sent to the active RoboticsDevice
                if self.active_device is None:
                    raise error.BadRequest("Attempted to execute control code with no selected device (missing SEL)")

                await self.devices[self.active_device].execute(ctrl)

        self.logger.info(f"Sequence complete")

    @staticmethod
    def control_from_string(ctrl: str) -> Control:
        """
        Construct a Control class from a string.
        """
        code = ctrl.strip().upper().split(" ")[0]
        if code not in CONTROL_MAP:
            raise error.BadRequest(f"Unknown control code: {ctrl}")

        return CONTROL_MAP[code](ctrl)

    @staticmethod
    def control_array_from_string(ctrl_list: str) -> list:
        """
        Construct a list of Control classes from a full control string.

        Control codes are delimited by a semi-colon (Control.DELIMITER).
        """
        arr = []
        cmds = ctrl_list.split(Control.DELIMITER)
        for cmd in cmds:
            arr.append(Robotics.control_from_string(cmd))
        return arr
