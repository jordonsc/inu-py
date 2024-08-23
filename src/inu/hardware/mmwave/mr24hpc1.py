"""
Seeed Studio MR24HPC1 24GHz Radar Sensor

User manual: https://files.seeedstudio.com/wiki/mmWave-radar/MR24HPC1_User_Manual-V1.5.pdf
Quick start: https://files.seeedstudio.com/wiki/mmWave-radar/MR24HPC1_Quick_Setup_Template-V1.0.pdf
"""
import asyncio
import logging

import machine
from inu.hardware import RadarSensor


class ControlCodes:
    # Core functions
    HEARTBEAT = b'\x01\x01'
    MODULE_RESET = b'\x01\x02'

    # Product information
    PRD_MODEL = b'\x02\xA1'
    PRD_INFO = b'\x02\xA2'
    HW_MODEL = b'\x02\xA3'
    FW_VERSION = b'\x02\xA4'

    # Work status
    INIT_COMPLETE = b'\x05\x01'
    SCENE = b'\x05\x07'
    SENSITIVITY = b'\x05\x08'
    STAT_INQ = b'\x05\x81'
    SCENE_INQ = b'\x05\x87'
    SENSITIVITY_INQ = b'\x05\x88'

    # Human presence detection
    PRESENCE_REPORT = b'\x80\x01'
    MOTION_REPORT = b'\x80\x02'
    MOVEMENT_REPORT = b'\x80\x03'
    NO_PERSON_REPORT = b'\x80\x0A'
    PROXIMITY_REPORT = b'\x80\x0B'

    # Information inquery
    PRESENCE_INQ = b'\x80\x81'
    MOTION_INQ = b'\x80\x82'
    MOVEMENT_INQ = b'\x80\x83'
    NO_PERSON_INQ = b'\x80\x8A'
    PROXIMITY_INQ = b'\x80\x8B'


class Scene:
    LIVING_ROOM = b'\x01'
    BEDROOM = b'\x02'
    BATHROOM = b'\x03'
    AREA = b'\x04'

    @staticmethod
    def from_room_size(room_size: int):
        if room_size >= 5:
            return Scene.LIVING_ROOM
        elif room_size == 4:
            return Scene.BEDROOM
        elif room_size == 3:
            return Scene.AREA
        else:
            return Scene.BATHROOM


class Sensitivity:
    LOW = b'\x01'
    MEDIUM = b'\x02'
    HIGH = b'\x03'

    @staticmethod
    def from_value(value: int):
        if value >= 3:
            return Sensitivity.HIGH
        elif value == 2:
            return Sensitivity.MEDIUM
        else:
            return Sensitivity.LOW


class Data:
    NO_DATA = b'\x0F'


class NoBodyDelay:
    NONE = b'\x00'
    SEC_10 = b'\x01'
    SEC_30 = b'\x02'
    MIN_1 = b'\x03'
    MIN_2 = b'\x04'
    MIN_5 = b'\x05'
    MIN_10 = b'\x06'
    MIN_30 = b'\x07'
    HR_1 = b'\x08'


class Mr24hpc1(RadarSensor):
    FRAME_HEADER = b'\x53\x59'
    FRAME_FOOTER = b'\x54\x43'

    def __init__(self, uart_index: int = 0):
        super().__init__()
        self.logger = logging.getLogger('inu.hw.mr24hpc1')
        self.uart = machine.UART(uart_index, baudrate=115200, stop=1, bits=8, parity=None)

    async def read_loop(self):
        self.logger.info("Starting read loop")

        while True:
            try:
                if self.uart.any():
                    self.read()
                else:
                    await asyncio.sleep(0.01)
            except Exception as e:
                self.logger.error(f"Error in read loop: {e}")

    def send_cmd(self, ctrl_code: bytes, data: bytes):
        self.logger.info(f"Sending command: {self.format_hex(ctrl_code)} :: {self.format_hex(data)}")

        payload = bytearray(self.FRAME_HEADER)
        payload.extend(ctrl_code)
        payload.extend(len(data).to_bytes(2, 'big'))
        payload.extend(data)
        checksum = sum(payload) & 0xFF
        payload.extend(checksum.to_bytes(1, 'big'))
        payload.extend(self.FRAME_FOOTER)

        self.uart.write(payload)
        self.uart.flush()

    def read(self):
        header = self.uart.read(2)

        if header is None:
            return

        if header != self.FRAME_HEADER:
            self.logger.error(f"Invalid frame header ({self.format_hex(header)})")
            self.flush_input()
            return

        ctrl_code = self.uart.read(2)
        data_len = int.from_bytes(self.uart.read(2), 'big')
        data = self.uart.read(data_len)
        checksum = int.from_bytes(self.uart.read(1), 'big')
        footer = self.uart.read(2)

        frame = bytearray(header)
        frame.extend(ctrl_code)
        frame.extend(data_len.to_bytes(2, 'big'))
        frame.extend(data)

        # Validate checksum
        checksum_calc = sum(frame) & 0xFF
        if checksum != checksum_calc:
            self.logger.error(f"Invalid checksum on frame ({self.format_hex(frame)}), expected {checksum_calc}")
            return

        frame.extend(checksum.to_bytes(1, 'big'))
        frame.extend(footer)

        # Validate footer
        if footer != self.FRAME_FOOTER:
            self.logger.error(f"Invalid frame footer ({self.format_hex(frame)})")
            return

        # Process frame
        try:
            self.process_frame(frame)
        except Exception as e:
            self.logger.error(f"Error processing frame: {e}")

    @staticmethod
    def format_hex(data: bytes):
        return " ".join(f"{byte:02X}" for byte in data)

    def flush_input(self):
        while self.uart.any():
            b = self.uart.read(1)
            self.logger.warning(f"Flushing: {self.format_hex(b)}")

    def process_frame(self, frame: bytearray):
        ctrl_code = frame[2:4]
        data_len = int.from_bytes(frame[4:6], 'big')
        data = frame[6:6 + data_len]

        # Heartbeat, do nothing
        if ctrl_code == ControlCodes.HEARTBEAT:
            self.logger.debug(f"<Heartbeat>")

        # Response to us configuring the device
        elif ctrl_code == ControlCodes.SCENE or ctrl_code == ControlCodes.SCENE_INQ:
            self.logger.debug(f"<Scene updated>")

        elif ctrl_code == ControlCodes.SENSITIVITY or ctrl_code == ControlCodes.SENSITIVITY_INQ:
            self.logger.debug(f"<Sensitivity updated>")

        elif ctrl_code == ControlCodes.NO_PERSON_REPORT or ctrl_code == ControlCodes.NO_PERSON_INQ:
            self.logger.debug(f"<No-body delay updated>")

        elif ctrl_code == ControlCodes.STAT_INQ:
            if data_len != 1:
                self.logger.error(f"Invalid data length for status report: {data_len}")
                return

            if data == b'\x01':
                self.logger.info(f"Init complete")
            elif data == b'\x02':
                self.logger.info(f"Init error")
            else:
                self.logger.info(f"Unknown init state: {data}")

        # Presence report: boolean yes/no if something is there
        # Reports on change.
        elif ctrl_code == ControlCodes.PRESENCE_REPORT or ctrl_code == ControlCodes.PRESENCE_INQ:
            if data_len != 1:
                self.logger.error(f"Invalid data length for presence report: {data_len}")
                return

            if data == b'\x00':
                present = False
                self.logger.info(f"No subject detected")
            elif data == b'\x01':
                present = True
                self.logger.info(f"Body detected")
            else:
                self.logger.error(f"Unknown presence state: {data}")
                return

            if self.radar.presence != present:
                if not present:
                    self.radar.clear_subject()
                else:
                    self.radar.presence = present

        # Motion report: basically same as the above but it will also tell if idle/moving
        # Reports on change.
        elif ctrl_code == ControlCodes.MOTION_REPORT or ctrl_code == ControlCodes.MOTION_INQ:
            if data_len != 1:
                self.logger.error(f"Invalid data length for motion report: {data_len}")
                return

            if data == b'\x00':
                motion = None
                self.logger.info(f"Motion: none")
            elif data == b'\x01':
                motion = False
                self.logger.info(f"Motion: idle")
            elif data == b'\x02':
                motion = True
                self.logger.info(f"Motion: active")
            else:
                self.logger.error(f"Unknown motion state: {data}")
                return

            if self.radar.motion != motion:
                if motion is None:
                    self.radar.clear_subject()
                else:
                    self.radar.motion = motion

        # Movement report: not actually the speed, it gives a value determining "how much" we're moving
        # This reports constantly every 1 second.
        elif ctrl_code == ControlCodes.MOVEMENT_REPORT or ctrl_code == ControlCodes.MOVEMENT_INQ:
            if data_len != 1:
                self.logger.error(f"Invalid data length for movement report: {data_len}")
                return

            speed = data[0]

            if speed == 0:
                # Zero-speed means no detections, we use None for this value on the radar object
                speed = None

            if self.radar.speed != speed:
                # Note that a value of 1 is used for an idle subject, so really the range is 2-100
                self.logger.debug(f"Speed: {speed}")
                self.radar.speed = speed

        # This is sort of an odd report, the values are "near" or "far" which the docs correlate to towards or
        # away from the sensor respectively. There is a 3-second evaluation period for this metric.
        # Reports on change.
        elif ctrl_code == ControlCodes.PROXIMITY_REPORT or ctrl_code == ControlCodes.PROXIMITY_INQ:
            if data_len != 1:
                self.logger.error(f"Invalid data length for proximity report: {data_len}")
                return

            if data == b'\x00':
                # unknown/chaotic/stationary
                direction = None
                self.logger.debug(f"Direction: unknown")
            elif data == b'\x01':
                # Approaching sensor for 3 seconds
                direction = True
                self.logger.debug(f"Direction: approaching")
            elif data == b'\x02':
                # Moving away from sensor for 3 seconds
                direction = False
                self.logger.debug(f"Direction: moving away")
            else:
                self.logger.error(f"Unknown proximity state: {self.format_hex(data)}")
                return

            if self.radar.direction != direction:
                self.radar.direction = direction

        # Anything else - not a big deal if we don't handle other control codes
        else:
            self.logger.warning(f"Unhandled control code: {self.format_hex(ctrl_code)}")
