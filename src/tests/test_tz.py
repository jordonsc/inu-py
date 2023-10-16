import time
import unittest
from datetime import date, datetime

from inu import tz
from inu.error import BadRequest


class TestTime(unittest.TestCase):
    def test_invalid(self):
        tests = [
            '2023-04-02T',
            '2023-04-02T12:23:23:00',
            '2023-04-02 UTC',
            '2023-04-02UTC',
            '2023-04-02+10',
            '2023-04-02+0',
            '2023-04-02+1000',
            '1.4d',
            '3m5m',
            '2d3.5h',
            '13',
            '',
            ' ',
            'foo bar',
        ]

        for test in tests:
            with self.assertRaises(BadRequest):
                tz.to_str(test)

    def test_abs(self):
        tests = [
            ['2023-04-02', '2023-04-02T00:00:00Z'],
            ['2023-04-02T20:04', '2023-04-02T20:04:00Z'],
            ['2023-04-02T20:04:30', '2023-04-02T20:04:30Z'],
            ['2023-04-02T20:04:30.343', '2023-04-02T20:04:30.343Z'],
        ]

        for test in tests:
            self.assertEqual(test[1], tz.to_str(test[0]))
            self.assertEqual(test[1], tz.to_str(test[0].lower()))
            self.assertEqual(test[1], tz.to_str(f"{test[0]}z"))
            self.assertEqual(test[1], tz.to_str(f"{test[0]}Z"))

    def test_today(self):
        today = date.today().strftime('%Y-%m-%d')

        tests = [
            ['20:04', f'{today}T20:04:00Z'],
            ['20:04:30', f'{today}T20:04:30Z'],
            ['20:04:30.343', f'{today}T20:04:30.343Z'],
        ]

        for test in tests:
            self.assertEqual(test[1], tz.to_str(test[0]))
            self.assertEqual(test[1], tz.to_str(test[0].lower()))
            self.assertEqual(test[1], tz.to_str(f"{test[0]}z"))
            self.assertEqual(test[1], tz.to_str(f"{test[0]}Z"))

    def test_relative(self):
        tests = [
            ['40s', 40],
            ['3m', (3 * 60)],
            ['3m6s', (3 * 60) + 6],
            ['3m 6s', (3 * 60) + 6],
            ['5M 1S', (5 * 60) + 1],
            ['2h3m', (2 * 3600) + (3 * 60)],
            ['2h3m20s', (2 * 3600) + (3 * 60) + 20],
            ['2h 3m 20s', (2 * 3600) + (3 * 60) + 20],
            ['19d 2h 3m 20s', (19 * 86400) + (2 * 3600) + (3 * 60) + 20],
            ['19d2h', (19 * 86400) + (2 * 3600)],
            ['19d3m', (19 * 86400) + (3 * 60)],
            ['1d120s', (1 * 86400) + 120],
        ]

        for test in tests:
            now = int(time.time())
            rel_time = tz.to_str(test[0])[:-1]
            delta = now - int(datetime.strptime(f"{rel_time} +0000", '%Y-%m-%dT%H:%M:%S %z').timestamp())

            self.assertEqual(test[1], delta)



