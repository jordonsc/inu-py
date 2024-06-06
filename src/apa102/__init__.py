from machine import SPI


class Apa102:
    PAYLOAD_SIZE = 4

    def __init__(self, num_leds, spi_index=1):
        self.num_leds = num_leds
        self.spi = SPI(spi_index)

        # Supply one extra clock cycle for each two pixels in the strip.
        end_header_size = num_leds // 16
        if num_leds % 16 != 0:
            end_header_size += 1

        self.buffer = bytearray((num_leds * self.PAYLOAD_SIZE) + end_header_size + self.PAYLOAD_SIZE)
        self.buffer[0:4] = b'\x00\x00\x00\x00'

        for i in range(num_leds * self.PAYLOAD_SIZE + self.PAYLOAD_SIZE, len(self.buffer)):
            self.buffer[i] = 0xff

    def set_led(self, i, r, g, b, x):
        x = min(max(x, 0), 31)
        index = self.PAYLOAD_SIZE + (i * self.PAYLOAD_SIZE)
        self.buffer[index] = 0xE0 | x
        self.buffer[index + 1] = b
        self.buffer[index + 2] = g
        self.buffer[index + 3] = r

    def fill(self, r, g, b, x=31, write=True):
        for i in range(self.num_leds):
            self.set_led(i, r, g, b, x)
        if write:
            self.write()

    def off(self):
        self.fill(0, 0, 0, write=True)

    def write(self):
        self.spi.write(self.buffer)
