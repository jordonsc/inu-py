import unittest

from micro_nats.protocol.cmd import client, server


class TestClientCommands(unittest.TestCase):
    def test_pub(self):
        self.assertEqual(
            client.Pub(subject=b"FOO.BAR", payload=b'abcdef').marshal(),
            b'PUB FOO.BAR 6\r\nabcdef\r\n'
        )

        self.assertEqual(
            client.Pub(subject="FOO.BAR", payload=b'abcdef').marshal(),
            b'PUB FOO.BAR 6\r\nabcdef\r\n'
        )

        self.assertEqual(
            client.Pub(subject="FOO.BAR").marshal(),
            b'PUB FOO.BAR 0\r\n\r\n'
        )

        self.assertEqual(
            client.Pub(subject=b"FOO.BAR", reply_to="BARRY").marshal(),
            b'PUB FOO.BAR BARRY 0\r\n\r\n'
        )

        self.assertEqual(
            client.Pub(subject="FOO.BAR", reply_to=b"BARRY", payload="hello world").marshal(),
            b'PUB FOO.BAR BARRY 11\r\nhello world\r\n'
        )


class TestServerCommands(unittest.TestCase):
    def test_msg(self):
        msg = server.Message(b'MSG subj sid 5\r\nhello\r\n')
        self.assertEqual(msg.get_subject(), b'subj')
        self.assertEqual(msg.get_sid(), "sid")
        self.assertEqual(msg.get_payload_size(), 5)
        self.assertEqual(msg.get_payload(), b'hello')

        hmsg = server.HeaderMessage.from_message(msg)
        self.assertEqual(hmsg.get_subject(), b'subj')
        self.assertEqual(hmsg.get_sid(), "sid")
        self.assertEqual(hmsg.get_payload_size(), 5)
        self.assertEqual(hmsg.get_payload(), b'hello')
        self.assertEqual(hmsg.get_headers_size(), 0)
        self.assertEqual(hmsg.get_headers(), b'')
