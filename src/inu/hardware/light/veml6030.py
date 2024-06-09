from . import AmbientLightSensor


class VEML6030(AmbientLightSensor):
    VEML6030_ADDR = 0x10
    ALS_CONF = 0x00
    REG_ALS = 0x04

    # initialise gain:1x, integration 100ms, persistence 1, disable interrupt
    DEFAULT_SETTINGS = b'\x00'

    def __init__(self, bus=None, freq=None, sda=None, scl=None, addr=VEML6030_ADDR):
        self.i2c = create_unified_i2c(bus=bus, freq=freq, sda=sda, scl=scl)
        self.addr = addr
        self.gain = 1
        self.res = 0.0576  # [lx/bit]
        self.i2c.writeto_mem(self.addr, VEML6030.ALS_CONF, VEML6030.DEFAULT_SETTINGS)
        sleep_ms(4)

    def read(self):
        try:
            data = self.i2c.readfrom_mem(self.addr, VEML6030.REG_ALS, 2)
        except:
            print(i2c_err_str.format(self.addr))
            return float('NaN')
        return int.from_bytes(data, 'little') * self.res

    def set_gain(self, g):
        """
        Set the gain of the sensor.

        :param g: One of: 0.125, 0.5, 1, 2
        :return:
        """
        if g == 0.125:
            conf = b'\x00\x10'
            self.res = 0.4608
        elif g == 0.25:
            conf = b'\x00\x18'
            self.res = 0.2304
        elif g == 1:
            conf = b'\x00\x00'
            self.res = 0.0576
        elif g == 2:
            conf = b'\x00\x08'
            self.res = 0.0288
        else:
            raise ValueError('Invalid gain. Accepted values: 0.125, 0.25, 1, 2')

        self.gain = g
        self.set_bits(VEML6030.ALS_CONF, conf, 'b\x18\x00')
        sleep_ms(4)

        return

    def set_bits(self, address, byte, mask):
        old_byte = int.from_bytes(self.i2c.readfrom_mem(self.addr, address, 2), 'little')
        temp_byte = old_byte
        int_byte = int.from_bytes(byte, "little")
        int_mask = int.from_bytes(mask, "big")

        # Cycle through each bit
        for n in range(16):
            bit_mask = (int_mask >> n) & 1
            if bit_mask == 1:
                if ((int_byte >> n) & 1) == 1:
                    temp_byte = temp_byte | 1 << n
                else:
                    temp_byte = temp_byte & ~(1 << n)

        new_byte = temp_byte
        self.i2c.writeto_mem(self.addr, address, new_byte.to_bytes(2, 'little'))
