import time

from inu.hardware.robotics.colour import ColourCode
from machine import SPI


class Apa102:
    PAYLOAD_SIZE = 4

    # Direction of effects.
    # The direction is superficial, "left" moves away from LED in position 0 toward the last LED.
    class DIRECTION:
        LEFT = 0
        RIGHT = 1

    def __init__(self, num_leds, spi_index=1):
        self.num_leds = num_leds
        self.spi = SPI(spi_index)

        # Segments are sub-sections of the LED strip that can be controlled independently.
        self.segments = {}
        self.selected_segment = None
        self.segment_start_index = 0
        self.segment_end_index = num_leds - 1

        # Supply one extra clock cycle for each two pixels in the strip.
        end_header_size = num_leds // 16
        if num_leds % 16 != 0:
            end_header_size += 1

        # Binary buffer sent to the SPI interface. We'll pre-set the header/footer and never overwrite it.
        self.buffer = bytearray((num_leds * self.PAYLOAD_SIZE) + end_header_size + self.PAYLOAD_SIZE)

        # Header
        self.buffer[0:4] = b'\x00\x00\x00\x00'

        # Footer
        for i in range(num_leds * self.PAYLOAD_SIZE + self.PAYLOAD_SIZE, len(self.buffer)):
            self.buffer[i] = 0xff

        # Memory of LED colour state - used to do fades, etc
        self.current_colour = {"": None, None: ColourCode("BLACK")}

        self.off()

    def create_segment(self, seg_id: str, start: int, end: int):
        """
        Create a segment of the LED strip. This is useful for chaining multiple strips and controlling them separately.

        :param seg_id: identifier for the segment
        :param start: start index of the segment, inclusive
        :param end: end index of the segment, inclusive
        :return:
        """
        if start < 0 or end >= self.num_leds:
            raise ValueError("Segment start/end out of range")

        self.segments[seg_id] = (start, end)
        self.current_colour[seg_id] = ColourCode("BLACK")

    def select_segment(self, seg_id: str | None):
        """
        Select a segment to operate on. All subsequent operations will be applied to this segment only.

        :param seg_id: Use None to clear the segment selection and use the entire strip.
        :return:
        """
        if seg_id is None:
            self.selected_segment = None
            self.segment_start_index = 0
            self.segment_end_index = self.num_leds - 1
            return

        if seg_id not in self.segments:
            raise ValueError("Segment not found")

        self.selected_segment = seg_id
        self.segment_start_index = self.segments[seg_id][0]
        self.segment_end_index = self.segments[seg_id][1]

    def set_led(self, i: int, col: ColourCode):
        """
        Set the colour of an LED.

        :param i: Index of LED
        :param col: Colour & brightness
        :return:
        """
        r, g, b, x = col.unpack()

        if i < 0:
            raise ValueError("LED index cannot be negative")

        i += self.segment_start_index

        if i > self.segment_end_index:
            raise ValueError("LED index out of range")

        # Convert brightness to 0-31 for APA102 devices
        x = Apa102.map(x)

        # Restrict bounds
        r = min(max(r, 0), 255)
        g = min(max(g, 0), 255)
        b = min(max(b, 0), 255)
        x = min(max(x, 0), 31)

        index = self.PAYLOAD_SIZE + (i * self.PAYLOAD_SIZE)
        self.buffer[index] = 0xE0 | x
        self.buffer[index + 1] = b
        self.buffer[index + 2] = g
        self.buffer[index + 3] = r

    def fill(self, col: ColourCode, write=True):
        """
        Fill the entire strip/segment with a single colour.

        :param col: Colour & brightness
        :param write: If true, will also write the buffer to the strip.
        :return:
        """
        for i in range(0, self.segment_end_index - self.segment_start_index + 1):
            self.set_led(i, col)

        self.current_colour[self.selected_segment] = col

        if write:
            self.write()

    def fade(self, col: ColourCode, duration: int):
        """
        Fade the entire strip/segment to a new colour.

        :param col: Colour & brightness
        :param duration: Duration of the fade in milliseconds
        :return:
        """
        base_col = self.current_colour[self.selected_segment]

        # Calculate the color difference per step
        dr = col.r - base_col.r
        dg = col.g - base_col.g
        db = col.b - base_col.b
        dx = col.x - base_col.x

        # Perform the fade
        start_time = time.time_ns()
        duration_ns = duration * 1000000
        while time.time_ns() < start_time + duration_ns:
            # Calculate the new color
            delta = (time.time_ns() - start_time) / duration_ns
            new_r = int(base_col.r + (dr * delta))
            new_g = int(base_col.g + (dg * delta))
            new_b = int(base_col.b + (db * delta))
            new_x = int(base_col.x + (dx * delta))

            # Set the new color for each LED
            for j in range(self.segment_start_index, self.segment_end_index + 1):
                self.set_led(j, ColourCode(new_r, new_g, new_b, new_x))

            # Write the new colors to the strip
            self.write()

        self.fill(col, write=True)

    def slide(self, col: ColourCode, duration: int, direction=DIRECTION.LEFT):
        """
        Slide the entire strip/segment to a new colour.

        :param col: Colour & brightness
        :param duration: Duration of the slide in milliseconds
        :param direction: Direction of effect
        :return:
        """
        start_time = time.time_ns()
        duration_ns = duration * 1000000
        while time.time_ns() < start_time + duration_ns:
            pos = (time.time_ns() - start_time) / duration_ns

            # Set the new color for each LED
            for j in range(self.segment_start_index, self.segment_end_index + 1):
                j_pos = (j - self.segment_start_index) / (self.segment_end_index - self.segment_start_index)

                # Adjust position calculation based on direction
                if direction == self.DIRECTION.RIGHT:
                    j_pos = 1 - j_pos

                if j_pos <= pos:
                    self.set_led(j, col)

            # Write the new colors to the strip
            self.write()

        self.fill(col, write=True)

    def pulse(self, col: ColourCode, duration: int, size: float = 0.1, direction=DIRECTION.LEFT):
        """
        Do a Cylon-style swipe across the strip/segment.

        :param col: Colour & brightness
        :param duration: Duration of the pulse in milliseconds
        :param size: Percentage of strip that the pulse will cover, 0.0-1.0
        :param direction: Direction of effect
        :return:
        """
        start_time = time.time_ns()
        duration_ns = duration * 1000000
        duration_exp = duration_ns * size  # How much we need to extend the position calcs to account for feathering
        base_col = self.current_colour[self.selected_segment]
        r, g, b, x = col.unpack()

        while time.time_ns() < start_time + duration_ns:
            pos = (time.time_ns() - start_time - duration_exp) / (duration_ns - (duration_exp * 2))

            # Set the new color for each LED
            for j in range(self.segment_start_index, self.segment_end_index + 1):
                j_pos = (j - self.segment_start_index) / (self.segment_end_index - self.segment_start_index)

                # Adjust position calculation based on direction
                if direction == self.DIRECTION.RIGHT:
                    j_pos = 1 - j_pos

                distance = abs(j_pos - pos)
                if distance > size:
                    # Too far from pulse point, write base colour
                    self.set_led(j, base_col)
                else:
                    # Inside pulse range, work out a delta
                    delta = 1 - (distance / size)
                    new_r = int(base_col.r + ((r - base_col.r) * delta))
                    new_g = int(base_col.g + ((g - base_col.g) * delta))
                    new_b = int(base_col.b + ((b - base_col.b) * delta))
                    new_x = int(base_col.x + ((x - base_col.x) * delta))
                    self.set_led(j, ColourCode(new_r, new_g, new_b, new_x))

            # Write the new colors to the strip
            self.write()

    def off(self, write=True):
        """
        Blank the entire strip/segment.
        """
        self.fill(ColourCode("BLACK"), write=write)

    def write(self):
        self.spi.write(self.buffer)

    @staticmethod
    def map(value, from_min=0, from_max=255, to_min=0, to_max=31):
        from_range = from_max - from_min
        to_range = to_max - to_min
        scaled_value = float(value - from_min) / float(from_range)
        return int(to_min + (scaled_value * to_range))
