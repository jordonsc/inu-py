import unittest

from micro_nats.util import Time


class TestTime(unittest.TestCase):
    def test_tz(self):
        fmt = Time.format_timestamp(1697432095)
        self.assertEqual(fmt, "2023-10-16T04:54:55.0Z")
