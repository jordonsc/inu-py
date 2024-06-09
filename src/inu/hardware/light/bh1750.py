import time

from machine import I2C
from . import AmbientLightSensor


class BH1750(AmbientLightSensor):
    # BH1750 I2C address
    I2C_ADDR = 0x23

    class CONFIG:
        CONTINUOUS_HIGH_RES_MODE = 0x10

    def __init__(self, i2c_id=1):
        self.i2c = I2C(i2c_id)
        self.config = bytearray(1)
        self.set_config(BH1750.CONFIG.CONTINUOUS_HIGH_RES_MODE)

    def read(self):
        data = self.i2c.readfrom(self.I2C_ADDR, 2)
        return ((data[0] << 8) | data[1]) / 1.2

    def set_config(self, config):
        self.config[0] = config
        self.i2c.writeto(self.I2C_ADDR, self.config)
        time.sleep(0.2)
