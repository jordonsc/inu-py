import asyncio
import logging
import time

from ... import error, Inu, const
from ...const import LogLevel

from .control import Control
from .control.common import Select, Wait, Trigger
from .control.actuator import Move
from .control.lights import Colour, Fx

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
    "TRG": Trigger,
    "TRIGGER": Trigger,
    "COL": Colour,
    "COLOUR": Colour,
    "COLOR": Colour,
    "FX": Fx,
}


class RoboticsDevice:
    """
    Base class for a physical device controller. Must be able to execute Control actions.
    """

    def __init__(self, inu=None, log_path="inu.robotics"):
        self.interrupted = False
        self.int_wait = False
        self.int_break = False
        self.inu = inu
        self.logger = logging.getLogger(log_path)

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

    def req_int(self):
        """
        Inform an active operation that it has been interrupted, expecting it to reverse action already taken and abort.
        """
        self.interrupted = True

    def req_wait(self):
        """
        Inform the current/next WAIT command to reset the timer.
        """
        self.int_wait = True

    def req_break(self):
        """
        Inform the current/next WAIT command to immediately break out of the delay.
        """
        self.int_break = True

    def select_component(self, component_id):
        """
        If supported, select a sub-component of the device. This is selected by using the Control code "SEL XX:YY",
        where YY could be the `component_id`.

        `None` will be used if the control selection does not include a component (eg. "SEL XX").
        """
        print("Select component", component_id)

    async def net_log(self, msg, level=LogLevel.INFO):
        if self.inu:
            await self.inu.log(msg, level)
        else:
            if level == LogLevel.DEBUG:
                self.logger.debug(msg)
            if level == LogLevel.INFO:
                self.logger.info(msg)
            elif level == LogLevel.WARNING:
                self.logger.warning(msg)
            elif level == LogLevel.ERROR:
                self.logger.error(msg)
            elif level == LogLevel.FATAL:
                self.logger.fatal(msg)


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

        # If the current operation has a request to interrupt, wait or break
        self.interrupted = False
        self.int_wait = False
        self.int_break = False

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
        self.devices[self.active_device].select_component(device.get_component())

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
        await self.run_list(Robotics.control_array_from_string(ctrl_str))
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

            # Common controls
            if isinstance(ctrl, Select):
                # Select device
                self.select_device(ctrl)
                last_sel = ctrl
            elif isinstance(ctrl, Wait):
                # Wait for a given time
                start_time = time.time_ns()
                while time.time_ns() - start_time < ctrl.get_time() * 1_000_000:
                    if self.interrupted:
                        # Interrupted, drop out so the INT process can begin
                        break
                    if self.int_wait:
                        # WAIT-reset requested, restart timer
                        start_time = time.time_ns()
                        self.int_wait = False
                    if self.int_break:
                        # WAIT-break requested, immediately drop out of WAIT delay
                        self.int_break = False
                        break
                    await asyncio.sleep(0.1)
            elif isinstance(ctrl, Trigger):
                # Dispatch a trigger message
                await self.inu.command(const.Subjects.COMMAND_TRIGGER, {
                    'code': ctrl.get_code(),
                })
                await asyncio.sleep(0.1)
            elif ctrl is None:
                # Error
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
        self.int_wait = False
        self.int_break = False
        self.allow_interrupt = False
        self.idle_time = time.time()

    async def run_int_list(self, control_list: list):
        """
        Runs a list of operations in reverse order and direction.
        """
        for ctrl in await self.prepare_int_list(control_list):
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

    async def prepare_int_list(self, control_list: list):
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

    def req_int(self) -> bool:
        """
        Interrupt the current operation, halting and reversing.

        Returns True if the interrupt was accepted.
        """
        if self.active_device and self.allow_interrupt:
            self.interrupted = True
            self.devices[self.active_device].req_int()
            return True
        else:
            return False

    def req_wait(self) -> bool:
        """
        Reset the current WAIT timer.

        Returns True if the wait was accepted.
        """
        if self.active_device:
            self.int_wait = True
            self.devices[self.active_device].req_wait()
            return True
        else:
            return False

    def req_break(self) -> bool:
        """
        Reset the current WAIT timer.

        Returns True if the wait was accepted.
        """
        if self.active_device:
            self.int_break = True
            self.devices[self.active_device].req_break()
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
