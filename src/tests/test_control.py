import unittest

from inu import error
from inu.hardware import robotics


class TestControlCodes(unittest.TestCase):
    def test_controls(self):
        controls = robotics.Robotics.control_array_from_string("SEL A0; mv 800 300; w 2000 int; MOVE -800 150 INT")

        self.assertEqual(4, len(controls))

        self.assertIsInstance(controls[0], robotics.Select)
        self.assertEqual("A0", controls[0].get_device())
        self.assertFalse(controls[0].allow_interrupt())

        self.assertIsInstance(controls[1], robotics.Move)
        self.assertEqual(800, controls[1].get_distance())
        self.assertEqual(300, controls[1].get_speed())
        self.assertFalse(controls[1].allow_interrupt())

        self.assertIsInstance(controls[2], robotics.Wait)
        self.assertEqual(2000, controls[2].get_time())
        self.assertTrue(controls[2].allow_interrupt())

        self.assertIsInstance(controls[3], robotics.Move)
        self.assertEqual(-800, controls[3].get_distance())
        self.assertEqual(150, controls[3].get_speed())
        self.assertTrue(controls[3].allow_interrupt())

    def test_fail(self):
        with self.assertRaises(error.BadRequest):
            robotics.Robotics.control_from_string("INT MOVE 4000 200")

        with self.assertRaises(error.Malformed):
            robotics.Robotics.control_from_string("MOVE 4000 INT")

        with self.assertRaises(error.BadRequest):
            robotics.Robotics.control_from_string("DANCE 500 100")
