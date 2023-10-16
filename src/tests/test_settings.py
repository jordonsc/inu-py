import unittest

from inu import error
from inu.schema import settings
from inu.schema.settings.sensors import MotionSensor, RangeTrigger


class TestSettings(unittest.TestCase):
    def test_settings(self):
        good_id = "motion.foo"
        bad_type = "sensor"
        bad_id = "motion"

        cls = settings.get_device_settings_class(
            settings.get_device_type_from_id(good_id)
        )
        self.assertEqual(cls, MotionSensor)
        self.assertNotEqual(cls, RangeTrigger)

        with self.assertRaises(error.UnsupportedDeviceType):
            settings.get_device_settings_class(bad_type)

        with self.assertRaises(error.InvalidDeviceId):
            settings.get_device_type_from_id(bad_id)
