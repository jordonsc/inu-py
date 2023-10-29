import asyncio
import logging
import time

import machine
from ..hardware import RangingSensor


class Sonar(RangingSensor):

    def __init__(self, uart: int = 1, tx: int = None, rx: int = None, baud: int = 9600):
        self.logger = logging.getLogger('inu.hw.sonar')
        self.uart = machine.UART(uart, baudrate=baud, tx=tx, rx=rx)

        self.distance: int | None = None
        self.last_measured: float | None = None

    def get_distance(self) -> int | None:
        """
        Returns the distance in mm.

        Returns None if no measurement has been made.
        """
        return self.distance

    def get_age(self) -> float | None:
        """
        Returns the number of seconds since the last valid measurement.

        Returns None if no measurement has been made.
        """
        if self.last_measured is None:
            return None

        return time.time() - self.last_measured

    @staticmethod
    def is_checksum_valid(data):
        cs = (data[0] + data[1] + data[2]) & 0x00ff
        return cs == data[3]

    async def read_loop(self):
        self.logger.debug("Starting read loop..")
        while True:
            if self.uart.any() >= 128:
                self.logger.warning("UART buffer overflow, flushing")
                await self.flush_uart()

            while self.uart.any() >= 4:
                data = self.uart.read(4)

                if data[0] != 0xff:
                    self.logger.warning(f"UART stream corrupted ({data[0]}), flushing")
                    await self.flush_uart()
                    continue

                if not self.is_checksum_valid(data):
                    self.logger.warning("Checksum error, flushing")
                    await self.flush_uart()
                    continue

                distance = data[1] * 256 + data[2]
                if distance > 0:
                    # a distance of exactly zero is a bad sensor reading
                    self.distance = distance
                    self.last_measured = time.time()

            await asyncio.sleep(0.01)

    async def flush_uart(self):
        buffer_size = self.uart.any()
        if buffer_size:
            self.uart.read(buffer_size)
            self.logger.warning(f"Flushed {buffer_size} bytes")
