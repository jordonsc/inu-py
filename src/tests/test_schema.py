import unittest

from inu.error import Malformed
from inu.schema import Alert
from inu.const import Priority


class TestSchema(unittest.TestCase):
    def test_schema(self):
        # No bootstrap - shouldn't raise despite not passing _validate()
        # TODO: reconsider this?
        Alert()

        with self.assertRaises(Malformed, msg="Priority cannot be None"):
            # Doesn't pass _validate()
            Alert({"message": "foo"})

        with self.assertRaises(Malformed, msg="Invalid type for schema bootstrap"):
            # Not a valid bootstrap
            Alert(32)

        alerts = [
            Alert(message="Test Message", priority=Priority.P2),
            Alert({"message": "Test Message", "priority": Priority.P2}),
            Alert({"message": "Test Message", "priority": 2}),
            Alert('{"message": "Test Message", "priority": 2}'),
        ]

        for alert in alerts:
            self.assertEqual(alert.message, "Test Message")
            self.assertEqual(alert.priority, Priority.P2)
