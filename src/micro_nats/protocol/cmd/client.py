import json
from . import CommandString, ClientCommand, SimpleClientCommand
from ...model import Model


class Ping(SimpleClientCommand):
    @classmethod
    def get_cmd(cls) -> bytes:
        return CommandString.PING


class Pong(SimpleClientCommand):
    @classmethod
    def get_cmd(cls) -> bytes:
        return CommandString.PONG


class Connect(ClientCommand, Model):
    @classmethod
    def get_cmd(cls) -> bytes:
        return CommandString.CONNECT

    def __init__(self, **args):
        self.verbose: bool = False
        self.pedantic: bool = True
        self.tls_required: bool = False
        self.auth_token: str | None = None
        self.user: str | None = None
        self.password: str | None = None  # NB: the actual field the payload is `pass`
        self.name: str | None = None
        self.lang: str = ""
        self.version: str = ""
        self.protocol: int = 0
        self.echo: bool | None = None
        self.sig: str | None = None
        self.jwt: str | None = None
        self.no_responders: bool | None = None
        self.headers: bool = True
        self.nkey: str | None = None

        super().__init__(**args)

    def marshal(self) -> bytes:
        d = {}
        for k in dir(self):
            if k[0] == '_':
                continue
            v = getattr(self, k)
            if callable(v):
                continue

            if k == "password":
                k = "pass"

            if v is not None:
                d[k] = v

        return f"CONNECT {json.dumps(d)}\r\n".encode()


class Pub(ClientCommand):
    @classmethod
    def get_cmd(cls) -> bytes:
        return CommandString.PUB

    def __init__(self, subject: str | bytes, payload: str | bytes = None, reply_to: str | bytes = None):
        self.subject = self.ensure_bytes(subject, allow_none=False)
        self.payload = self.ensure_bytes(payload)
        self.reply_to = self.ensure_bytes(reply_to)

    def marshal(self) -> bytes:
        payload = self.payload if self.payload else b''
        payload_size = str(len(payload)).encode() if payload else b'0'

        if self.reply_to:
            return CommandString.PUB + b' ' + self.subject + b' ' + self.reply_to + b' ' + payload_size + b'\r\n' + \
                   payload + b'\r\n'
        else:
            return CommandString.PUB + b' ' + self.subject + b' ' + payload_size + b'\r\n' + payload + b'\r\n'


class Sub(ClientCommand):
    @classmethod
    def get_cmd(cls) -> bytes:
        return CommandString.SUB

    def __init__(self, subject: str | bytes, sid: str | bytes, queue_grp: str | bytes = None):
        self.subject = self.ensure_bytes(subject, allow_none=False)
        self.sid = self.ensure_bytes(sid, allow_none=False)
        self.queue_grp = self.ensure_bytes(queue_grp)

    def marshal(self) -> bytes:
        if self.queue_grp:
            return CommandString.SUB + b' ' + self.subject + b' ' + self.queue_grp + b' ' + self.sid + b'\r\n'
        else:
            return CommandString.SUB + b' ' + self.subject + b' ' + self.sid + b'\r\n'


class Unsub(ClientCommand):
    @classmethod
    def get_cmd(cls) -> bytes:
        return CommandString.UNSUB

    def __init__(self, sid: str | bytes, max_messages: int | None = None):
        self.sid = self.ensure_bytes(sid, allow_none=False)
        self.max_messages = max_messages

    def marshal(self) -> bytes:
        if self.max_messages:
            return CommandString.UNSUB + b' ' + self.sid + b' ' + str(self.max_messages).encode() + b' ' + b'\r\n'
        else:
            return CommandString.UNSUB + b' ' + self.sid + b' ' + b'\r\n'
