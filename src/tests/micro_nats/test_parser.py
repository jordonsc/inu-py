import unittest

from micro_nats import error
from micro_nats.model import Server
from micro_nats.util import headers, uri


class TestUri(unittest.TestCase):
    def test_uri(self):
        svr = uri.parse_server("nats://1.2.3.4:5000")
        self.assertEqual(svr.proto, Server.Protocol.NATS)
        self.assertEqual(svr.address, "1.2.3.4")
        self.assertEqual(svr.port, 5000)

        svr = uri.parse_server("nats://my.hostname:69")
        self.assertEqual(svr.proto, Server.Protocol.NATS)
        self.assertEqual(svr.address, "my.hostname")
        self.assertEqual(svr.port, 69)

        svr = uri.parse_server("nats://foo")
        self.assertEqual(svr.proto, Server.Protocol.NATS)
        self.assertEqual(svr.address, "foo")
        self.assertEqual(svr.port, Server.DEFAULT_PORT)

        bad_servers = [
            "NATS://foo",
            "nats://foo:bar"
            "nats://foo:123:123"
            "hostname"
            "hostname:port"
        ]

        for bad in bad_servers:
            with self.assertRaises(error.Malformed):
                uri.parse_server(bad)


class TestParseHeaders(unittest.TestCase):
    def test_parse(self):
        hdrs = headers.parse_headers('Foo: bar\r\nHello: world\r\n')
        self.assertEqual(len(hdrs), 2)

        self.assertEqual(hdrs["Foo"], "bar")
        self.assertEqual(hdrs["Hello"], "world")

        hdrs = headers.parse_headers(
            b'NATS/1.0 100\r\nNats-Last-Consumer: 0\r\nNats-Last-Stream: 34'
        )
        self.assertEqual(len(hdrs), 4)

        self.assertEqual(hdrs[headers.Headers.PROTOCOL], "NATS/1.0")
        self.assertEqual(hdrs[headers.Headers.STATUS_CODE], "100")
        self.assertNotIn(headers.Headers.STATUS_DESC, hdrs)

        self.assertEqual(hdrs["Nats-Last-Consumer"], "0")
        self.assertEqual(hdrs["Nats-Last-Stream"], "34")

        hdrs = headers.parse_headers(
            b'NATS/1.0 100 Idle Heartbeat\r\nNats-Last-Consumer: 1\r\nNats-Last-Stream: 35\r\n\r\n'
        )
        self.assertEqual(len(hdrs), 5)

        self.assertEqual(hdrs[headers.Headers.PROTOCOL], "NATS/1.0")
        self.assertEqual(hdrs[headers.Headers.STATUS_CODE], "100")
        self.assertEqual(hdrs[headers.Headers.STATUS_DESC], "Idle Heartbeat")

        self.assertEqual(hdrs["Nats-Last-Consumer"], "1")
        self.assertEqual(hdrs["Nats-Last-Stream"], "35")

        with self.assertRaises(error.Malformed):
            headers.parse_headers(b'NATS/1.0\r\nNats-Last-Consumer: 1\r\nNats-Last-Stream: 35\r\n\r\n')

        with self.assertRaises(error.Malformed):
            headers.parse_headers(b'NATS/1.0 100\r\nFoo:bar\r\nNats-Last-Stream: 35\r\n\r\n')
