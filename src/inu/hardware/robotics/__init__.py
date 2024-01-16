import asyncio
import logging
import time

from ... import error, Inu
from ...const import LogLevel


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

    def allow_interrupt(self) -> bool:
        """
        Select Controls have no concept of interrupts but should not block the interrupt chain.
        """
        return True

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

    def __init__(self):
        self.interrupted = False

    async def execute(self, ctrl: Control, reverse: bool = False):
        """
        Run a control code. Non-tangible controls like SEL and WAIT will not be sent to a RoboticsDevice.

        `reverse` will undo a Control operation, while also ignoring further interrupts.
        """
        self.interrupted = False

    def set_power(self, powered: bool):
        """
        Powers or un-powers the device. May do nothing depending on if the device has a passive power state.
        """
        pass

    def interrupt(self):
        """
        Inform an active operation that it has been interrupted, expecting it to reverse action already taken and abort.
        """
        self.interrupted = True


class Robotics:
    """
    Robotics manager service.
    """

    def __init__(self, inu: Inu, power_up_delay=2500):
        self.inu = inu
        self.devices = {}
        self.logger = logging.getLogger("inu.robotics")

        # Master power state
        self.powered = False
        self.power_up_delay = power_up_delay
        self.idle_time = time.time()

        # Currently selected device (eg "A0")
        self.active_device = None

        # If the current operation has been interrupted
        self.interrupted = False

        # If the current operation _allows_ interruption
        self.allow_interrupt = False

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
        self.powered = powered

        for device in self.devices.values():
            device.set_power(powered)

    async def run(self, ctrl_str: str):
        """
        Run a control code string.
        """
        self.reset_state()
        await self.run_list(self.control_array_from_string(ctrl_str))
        self.reset_state()

    async def run_list(self, control_list: list):
        """
        Run a list of operations.
        """
        int_chain = []
        last_sel = None

        # Brings device power online if it was not already
        await self.ready_devices()

        for ctrl in control_list:
            await self.inu.log(f"EXEC: {ctrl}", LogLevel.DEBUG)
            await asyncio.sleep(0)

            if ctrl.allow_interrupt():
                int_chain.append(ctrl)
                self.allow_interrupt = True
            else:
                int_chain.clear()
                self.allow_interrupt = False

                if last_sel:
                    # Important: we need to remember the last select for reversing
                    int_chain.append(last_sel)

            # Non-tangible codes -
            if isinstance(ctrl, Select):
                self.select_device(ctrl)
                last_sel = ctrl
            elif isinstance(ctrl, Wait):
                await asyncio.sleep(ctrl.get_time() / 1000)
            elif ctrl is None:
                await self.inu.log("Null control code provided", LogLevel.WARNING)
            else:
                # Tangible codes need to be sent to the active RoboticsDevice
                if self.active_device is None:
                    raise error.BadRequest("Attempted to execute control code with no selected device (missing SEL)")

                await self.devices[self.active_device].execute(ctrl)

            if self.interrupted:
                # Run the int_chain in reverse order..
                self.reset_state()
                await self.inu.log("Reversing ops..", LogLevel.DEBUG)
                await self.run_int_list(int_chain)

                # then run it again in normal order
                self.reset_state()
                await self.inu.log("Replaying interrupted ops..", LogLevel.DEBUG)
                await self.run_list(int_chain)
                await self.inu.log("INT seq completed", LogLevel.DEBUG)

    async def ready_devices(self):
        """
        If system is unpowered, then power it up and wait for `warmup_delay` ms.
        Resets idle time.
        """
        if not self.powered:
            self.set_power(True)
            await asyncio.sleep(self.power_up_delay / 1000)

    def reset_state(self):
        """
        Clears device state from a previous run.
        """
        self.active_device = None
        self.interrupted = False
        self.allow_interrupt = False
        self.idle_time = time.time()

    async def run_int_list(self, control_list: list):
        """
        Runs a list of operations in reverse order and direction.
        """
        for ctrl in self.prepare_int_list(control_list):
            await self.inu.log(f"REV EXEC: {ctrl}", LogLevel.DEBUG)
            await asyncio.sleep(0)

            # Non-tangible codes -
            if isinstance(ctrl, Select):
                self.select_device(ctrl)
            elif isinstance(ctrl, Wait):
                await asyncio.sleep(ctrl.get_time() / 1000)
            elif ctrl is None:
                pass
            else:
                # Tangible codes need to be sent to the active RoboticsDevice
                if self.active_device is None:
                    raise error.BadRequest("Missing SEL in INT list")

                await self.devices[self.active_device].execute(ctrl, reverse=True)

    def prepare_int_list(self, control_list: list):
        """
        Reverse the list, moving SEL statements to the front of their controls.

        Skips Wait controls.
        """
        int_list = []
        buffer = []
        # Skip the last element as that would have been partially completed and already reversed
        for ctrl in reversed(control_list[:-1]):
            if isinstance(ctrl, Select):
                int_list.append(ctrl)
                int_list += buffer
                buffer = []
            elif isinstance(ctrl, Wait) or ctrl is None:
                pass
            else:
                buffer.append(ctrl)

        if len(buffer) > 0:
            await self.inu.log("INT list has no preceding SEL", LogLevel.WARNING)
            int_list += buffer

        return int_list

    def interrupt(self) -> bool:
        """
        Interrupt the current operation, halting and reversing.

        Returns True if the interrupt was accepted.
        """
        if self.active_device and self.allow_interrupt:
            self.interrupted = True
            self.devices[self.active_device].interrupt()
            return True
        else:
            return False

    def get_idle_time(self) -> float:
        """
        Returns the time in seconds that the device has been idle.
        """
        return time.time() - self.idle_time

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
