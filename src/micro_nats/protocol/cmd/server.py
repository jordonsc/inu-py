import json
from . import CommandString, SimpleServerCommand, PayloadCommand
from ... import error


class Ping(SimpleServerCommand):
    @classmethod
    def get_cmd(cls) -> bytes:
        return CommandString.PING


class Pong(SimpleServerCommand):
    @classmethod
    def get_cmd(cls) -> bytes:
        return CommandString.PONG


class OK(SimpleServerCommand):
    @classmethod
    def get_cmd(cls) -> bytes:
        return CommandString.OK


class Error(PayloadCommand):
    @classmethod
    def get_cmd(cls) -> bytes:
        return CommandString.ERR

    def get_raw(self) -> bytes:
        """
        Raw message data as bytes.
        """
        return self.payload

    def get_error(self) -> str:
        """
        Error message as a string.
        """
        return self.payload.decode()


class Info(PayloadCommand):
    @classmethod
    def get_cmd(cls) -> bytes:
        return CommandString.INFO

    def get_raw(self) -> bytes:
        """
        INFO payload as a byte-array, containing a JSON-formatted string.
        """
        return self.payload

    def get_info(self) -> dict:
        """
        Parsed JSON payload as a dict.
        """
        return json.loads(self.payload.decode())


class Message(PayloadCommand):
    @classmethod
    def get_cmd(cls) -> bytes:
        return CommandString.MSG

    def __init__(self, data: bytes):
        data = self.ensure_bytes(data, allow_none=False)
        super().__init__(data, find_end=False)

        pos_primary = data.find(b'\r\n', 4)
        if pos_primary == -1:
            raise error.ParseError(f"Malformed MSG payload")

        primary = data[4:pos_primary]
        parts = primary.split(b' ')
        if len(parts) < 3:
            raise error.ParseError(f"Required arguments for MSG payload insufficient")

        self.subject = parts[0]
        self.sid = parts[1]
        self.reply_to = parts[2] if len(parts) >= 4 else None

        try:
            self.payload_size = int(parts[3] if len(parts) >= 4 else parts[2])
        except ValueError:
            raise error.ParseError("MSG payload size invalid")

        if len(data) < pos_primary + self.payload_size + 4:
            # Good chance we just need another packet
            raise error.IncompletePayload(f"Insufficient data available for message payload")

        pos_secondary = pos_primary + 2 + self.payload_size

        self.payload = data[pos_primary + 2:pos_secondary]
        if len(self.payload) < self.payload_size:
            raise error.IncompletePayload("Incomplete payload")
        elif len(self.payload) > self.payload_size:
            raise error.Malformed("Payload size too large")

        self._consumed = pos_secondary + 2

    def get_subject(self) -> bytes:
        return self.subject

    def get_sid_raw(self) -> bytes:
        return self.sid

    def get_sid(self) -> str:
        return self.sid.decode()

    def get_reply_to(self) -> bytes | None:
        return self.reply_to

    def get_payload(self) -> bytes:
        return self.payload

    def get_payload_size(self) -> int:
        return self.payload_size


class HeaderMessage(PayloadCommand):
    @classmethod
    def get_cmd(cls) -> bytes:
        return CommandString.HMSG

    @classmethod
    def from_message(cls, msg: Message):
        return cls((msg.subject, msg.sid, msg.reply_to, msg.payload))

    def __init__(self, data: bytes | tuple):
        if isinstance(data, tuple):
            self.subject, self.sid, self.reply_to, self.payload = data
            self.payload_size = len(self.payload)
            self.headers_size = 0
            self.headers = b''
            return

        data = self.ensure_bytes(data, allow_none=False)
        super().__init__(data, find_end=False)

        pos_primary = data.find(b'\r\n', 5)
        if pos_primary == -1:
            raise error.ParseError(f"Malformed HMSG payload")

        primary = data[5:pos_primary]
        parts = primary.split(b' ')
        if len(parts) < 3:
            raise error.ParseError(f"Required arguments for HMSG payload insufficient")

        self.subject = parts[0]
        self.sid = parts[1]
        self.reply_to = parts[2] if len(parts) >= 5 else None

        try:
            self.headers_size = int(parts[3] if len(parts) >= 5 else parts[2])
            self.payload_size = int(parts[4] if len(parts) >= 5 else parts[3]) - self.headers_size
        except ValueError:
            raise error.ParseError("HMSG header/payload size invalid")

        if len(data) < pos_primary + self.payload_size + 4:
            # Good chance we just need another packet
            raise error.IncompletePayload(f"Insufficient data available for message payload")

        pos_headers = pos_primary + 2 + self.headers_size
        self.headers = data[pos_primary + 2:pos_headers]
        if len(self.headers) != self.headers_size:
            raise error.IncompletePayload(f"Incomplete headers")
        elif len(self.headers) > self.headers_size:
            raise error.Malformed("Header size too large")

        pos_payload = pos_headers + self.payload_size
        self.payload = data[pos_headers:pos_payload]
        if len(self.headers) != self.headers_size:
            raise error.IncompletePayload(f"Incomplete payload")
        elif len(self.payload) > self.payload_size:
            raise error.Malformed("Payload size too large")

        self._consumed = pos_payload + 2

    def get_subject(self) -> bytes:
        return self.subject

    def get_sid_raw(self) -> bytes:
        return self.sid

    def get_sid(self) -> str:
        return self.sid.decode()

    def get_reply_to(self) -> bytes | None:
        return self.reply_to

    def get_headers(self) -> bytes:
        return self.headers

    def get_headers_size(self) -> int:
        return self.headers_size

    def get_payload(self) -> bytes:
        return self.payload

    def get_payload_size(self) -> int:
        return self.payload_size
