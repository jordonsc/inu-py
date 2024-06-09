import time
from machine import I2C
from . import AmbientLightSensor


class VEML6030(AmbientLightSensor):
    # VEML6030 I2C address
    I2C_ADDR = 0x10

    # Configuration register
    ALS_CONF = 0x00  # Ambient Light Sensor (ALS) configuration register

    # lux/bit
    RESOLUTION = 0.0576

    class GAIN:
        GAIN_1 = 0x00  # Gain x1
        GAIN_2 = 0x01  # Gain x2
        GAIN_1_8 = 0x02  # Gain x1/8
        GAIN_1_4 = 0x03  # Gain x1/4

    def __init__(self, i2c_id=1, gain=GAIN.GAIN_1):
        self.i2c = I2C(i2c_id)
        self.config = bytearray(2)
        self.set_config(gain)  # Set ALS gain and integration time

    def read(self):
        # Read ALS data from 0x04 register
        data = self.i2c.readfrom_mem(self.I2C_ADDR, 0x04, 2)
        return ((data[0] << 8) | data[1]) * VEML6030.RESOLUTION

    def set_config(self, value):
        self.config[0] = value & 0xFF
        self.config[1] = (value >> 8) & 0xFF
        self.i2c.writeto_mem(self.I2C_ADDR, VEML6030.ALS_CONF, self.config)
        time.sleep(0.2)
