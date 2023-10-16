import unittest

from micro_nats.jetstream.protocol.stream import StreamInfo, StreamState


class TestClientCommands(unittest.TestCase):
    def test_cascase(self):
        data = {
            "type": "io.nats.jetstream.api.v1.stream_info_response", "total": 0, "offset": 0, "limit": 0,
            "config": {
                "name": "logs", "subjects": ["inu.log.\u003e"], "retention": "limits", "max_consumers": -1,
                "max_msgs": -1, "max_bytes": -1, "max_age": 0, "max_msgs_per_subject": 100000,
                "max_msg_size": -1, "discard": "old", "storage": "file", "num_replicas": 1,
                "duplicate_window": 120000000000, "allow_direct": False, "mirror_direct": False,
                "sealed": False, "deny_delete": False, "deny_purge": False, "allow_rollup_hdrs": False
            },
            "created": "2023-09-13T04:07:00.065753231Z",
            "state": {
                "messages": 47, "bytes": 5443, "first_seq": 1, "first_ts": "2023-09-13T04:07:00.070209252Z",
                "last_seq": 47, "last_ts": "2023-09-29T04:42:35.262906254Z", "num_subjects": 34,
                "consumer_count": 0
            },
            "cluster": {
                "leader": "NDWYDQZ7G6MICHEP4HL5ACSGJUCMQJWXPWDNREDLH545AZPDHRB7YRA3"
            }
        }

        info = StreamInfo(**data)
        self.assertEqual(info.created, "2023-09-13T04:07:00.065753231Z")
        self.assertTrue(isinstance(info.state, StreamState))
        self.assertEqual(info.state.messages, 47)

