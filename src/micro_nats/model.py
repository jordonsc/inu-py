import base64
import json
import random
from .util import headers, Time

CLIENT_LANGUAGE = "python"
CLIENT_VERSION = "1.0.0"


class Model:
    def __init__(self, **args):
        super().__init__()
        self.hydrate(args)

    def hydrate(self, items: dict[str, any]):
        for k, v in items.items():
            if k[0] != '_' and not callable(v) and hasattr(self, k):
                current = getattr(self, k)
                if isinstance(v, dict) and isinstance(current, Model):
                    # Cascade creation of child Model objects
                    setattr(self, k, type(current)(**v))
                else:
                    setattr(self, k, v)

    def as_dict(self):
        d = {}

        for k in dir(self):
            if k[0] == '_':
                continue

            v = getattr(self, k)

            if callable(v):
                continue

            if isinstance(v, Model):
                v = v.as_dict()

            if v is not None:
                d[k] = v

        return d

    def to_json(self):
        return json.dumps(self.as_dict())


class Server(Model):
    class Protocol:
        NATS = "nats"

    DEFAULT_PORT = 4222

    def __init__(self, address: str, port: int = DEFAULT_PORT, proto: str = Protocol.NATS, **args):
        super().__init__(**args)

        self.address = address
        self.port = port
        self.proto = proto


class ServerContext(Model):
    """
    Represents information about server connection properties relevant for a NATS client.
    """

    def __init__(self, servers: str | list[str], **args):
        # Server connection parameters
        self.servers: str | list[str] = servers
        self.shuffle_servers: bool = True

        self.connect_timeout: float = 5.0
        self.reconnect_delay: float = 1.0
        self.auto_reconnect: bool = True

        self.ping_interval: float = 15.0
        self.max_missed_pings: int = 2

        # Handshake & authentication
        self.client_name: str | None = None
        self.verbose_mode: bool = False

        self.auth_token: str | None = None
        self.auth_user: str | None = None
        self.auth_pass: str | None = None
        self.auth_jwt: str | None = None
        self.auth_nkey: str | None = None

        super().__init__(**args)

        if self.shuffle_servers:
            self.shuffle_server_list()

    def server_count(self) -> int:
        """
        Return the number of available servers provided in the context.
        """
        if isinstance(self.servers, list):
            return len(self.servers)
        elif isinstance(self.servers, str):
            return 1
        else:
            return 0

    def shuffle_server_list(self):
        """
        Randomly shuffle the server list.

        Does nothing if a string is provided for the server list.
        """
        if not isinstance(self.servers, list):
            return

        svr_count = self.server_count()
        if svr_count <= 1:
            return

        for i in range(svr_count - 1):
            j = random.randrange(i, svr_count)
            self.servers[i], self.servers[j] = self.servers[j], self.servers[i]

    def cycle_servers(self):
        """
        Cycle the list of servers in order.

        Does nothing if a string is provided for the server list.
        """
        if not isinstance(self.servers, list):
            return

        svr = self.servers.pop(0)
        self.servers.append(svr)

    def get_server(self, cycle: bool = True) -> str:
        """
        Return the next server in the list.
        """
        if isinstance(self.servers, list):
            svr = self.servers[0]

            if cycle:
                self.cycle_servers()

            return svr
        else:
            return self.servers


class ServerInfo(Model):
    def __init__(self, **args):
        self.server_id: str | None = None
        self.server_name: str | None = None
        self.version: str | None = None
        self.go: str | None = None
        self.host: str | None = None
        self.port: int | None = None
        self.headers: bool | None = None
        self.max_payload: int | None = None
        self.proto: int | None = None
        self.auth_required: bool | None = None
        self.tls_required: bool | None = None
        self.tls_verify: bool | None = None
        self.tls_available: bool | None = None
        self.connect_urls: list[str] | None = None
        self.ws_connect_urls: list[str] | None = None
        self.ldm: bool | None = None
        self.git_commit: str | None = None
        self.jetstream: bool | None = None
        self.ip: str | None = None
        self.client_id: str | None = None
        self.client_ip: str | None = None
        self.nonce: str | None = None
        self.cluster: str | None = None
        self.domain: str | None = None

        super().__init__(**args)

    @classmethod
    def from_info(cls, info):
        from .protocol.cmd.server import Info
        if not isinstance(info, Info):
            raise ValueError("Cannot construct from a non `cmd.Info` object")

        return cls(**info.get_info())

    def __repr__(self):
        return f"<nats version={self.version}; jetstream={self.jetstream}>"


class Message:
    """
    Represents a message from a NATS subscription.
    """

    def __init__(self, msg=None):
        from .protocol.cmd import server as s_cmd

        self.stream_seq: int | None = None
        self.consumer_seq: int | None = None
        self.time: str | None = None
        self.time_ns: int | None = None

        if msg is None:
            self.payload = None
            self.subject = None
            self.reply_to = None
            self.headers = {}
            return

        if not isinstance(msg, s_cmd.Message) and not isinstance(msg, s_cmd.HeaderMessage):
            raise ValueError("Message constructor must be a server Message or HeaderMessage")

        self.payload: bytes = msg.get_payload()
        self.subject: str = msg.get_subject().decode()
        self.reply_to: str = msg.get_reply_to().decode() if msg.get_reply_to() else None

        self.infer_sequence()

        if isinstance(msg, s_cmd.HeaderMessage):
            self.headers = headers.parse_headers(msg.get_headers())
        else:
            self.headers = {}

    def __repr__(self):
        return f"<message subject={self.get_subject()}; headers={json.dumps(self.headers)}; " + \
               f"payload={self.get_payload().decode()}>"

    def infer_sequence(self):
        """
        The stream sequence, consumer sequence and message time are in the reply-to string. If available, attempt to
        infer these values from the reply-to.
        """
        if not self.reply_to:
            return

        parts = self.reply_to.split(".")
        if len(parts) < 8:
            return

        self.time = Time.format_msg_timestamp(parts[-2])
        self.time_ns = int(parts[-2])
        self.consumer_seq = int(parts[-3])
        self.stream_seq = int(parts[-4])

    def get_payload(self) -> bytes:
        return self.payload

    def from_json(self) -> dict:
        return json.loads(self.payload.decode())

    def get_subject(self) -> str:
        return self.subject

    def get_reply_to(self) -> str | None:
        return self.reply_to

    def get_headers(self) -> dict:
        return self.headers

    def has_header(self, header: str):
        return header in self.headers

    def get_header(self, header: str) -> str:
        return self.headers[header]

    def status_code(self) -> int:
        if self.has_header(headers.Headers.STATUS_CODE):
            try:
                return int(self.get_header(headers.Headers.STATUS_CODE))
            except ValueError:
                return 0
        else:
            return 0

    def status_description(self) -> str:
        if self.has_header(headers.Headers.STATUS_DESC):
            return self.get_header(headers.Headers.STATUS_DESC)
        else:
            return ""

    def get_header_or(self, header: str, default: any):
        if self.has_header(header):
            return self.headers[header]
        else:
            return default

    def can_ack(self) -> bool:
        return self.reply_to is not None and len(self.reply_to) > 0

    @classmethod
    def from_stream(cls, stream_message):
        from .jetstream.protocol import stream, ErrorResponse

        if isinstance(stream_message, stream.StreamMessageResponse):
            # by default, the server sends a pretty useless wrapper - dive in one deeper
            stream_message = stream_message.message

        if isinstance(stream_message, ErrorResponse):
            # if the API returned an error, just pass it along
            return stream_message

        assert isinstance(stream_message, stream.StreamMessage), "stream_message must be an instance of StreamMessage"

        msg = cls()
        msg.payload = base64.b64decode(stream_message.data)
        msg.subject = stream_message.subject
        msg.time = stream_message.time
        msg.stream_seq = stream_message.seq

        return msg
