from ... import error


class CommandString:
    # Common commands
    PING = b'PING'
    PONG = b'PONG'

    # Server -> client commands
    INFO = b'INFO'
    OK = b'+OK'
    ERR = b'-ERR'
    MSG = b'MSG'
    HMSG = b'HMSG'

    # Client -> server commands
    CONNECT = b'CONNECT'
    PUB = b'PUB'
    HPUB = b'HPUB'
    SUB = b'SUB'
    UNSUB = b'UNSUB'


class Command:
    """
    Abstract class for command parsers.
    """

    @classmethod
    def get_cmd(cls) -> bytes:
        """
        Return the message header.

        eg. b"PING"
        """
        pass

    @staticmethod
    def ensure_bytes(data: str | bytes | bytearray | None, allow_none: bool = True) -> bytes | None:
        if data is None:
            if allow_none:
                return None
            else:
                raise ValueError("None type is not permitted here")

        if isinstance(data, bytes):
            return data
        elif isinstance(data, str):
            return data.encode()
        elif isinstance(data, bytearray):
            return bytes(data)
        else:
            raise ValueError(f"Not a valid bytes-capable type: {type(data)} [{data}]")


class ServerCommand(Command):
    """
    A message sent by the server and received by the client.
    """

    @classmethod
    def is_match(cls, data: bytes) -> bool:
        """
        Checks if this command is next in the buffer array.
        """
        cmd_size = len(cls.get_cmd())
        return len(data) >= (cmd_size + 2) and data[:cmd_size] == cls.get_cmd()

    def consumed(self) -> int:
        """
        The number of bytes consumed by parsing this message.

        This should always be at least len(get_cmd()) + 2.
        """
        return self._consumed

    def __init__(self, _: bytes):
        """
        Parse a payload, populating attributes.
        """
        self._consumed = 0


class ClientCommand(Command):
    """
    A message sent by the client and received by the server
    """

    def marshal(self) -> bytes:
        raise NotImplementedError()


class SimpleServerCommand(ServerCommand):
    """
    A server command with no payload.
    """

    def __init__(self, data: bytes):
        super().__init__(data)

        if not self.is_match(data):
            raise error.ParseError(f"Not a {self.get_cmd()} payload")

        cmd_size = len(self.get_cmd())
        if data[cmd_size:cmd_size + 2] == b'\r\n':
            self._consumed = cmd_size + 2
        else:
            raise error.ParseError(f"Unexpected data in {self.get_cmd()} payload")


class SimpleClientCommand(ClientCommand):
    """
    A client command with no payload.
    """

    def marshal(self) -> bytes:
        return self.get_cmd() + b'\r\n'


class PayloadCommand(ServerCommand):
    """
    A command with a payload included.
    """

    def __init__(self, data: bytes, find_end: bool = True):
        super().__init__(data)

        if not self.is_match(data):
            raise error.ParseError(f"Not a {self.get_cmd()} payload")

        cmd_size = len(self.get_cmd())
        if data[cmd_size] != 32:
            raise error.ParseError(f"Malformed payload for {self.get_cmd()} message")

        if not find_end:
            return

        pos = data.find(b'\r\n', cmd_size + 1)
        if pos == -1:
            raise error.IncompletePayload(f"Missing end of payload for {self.get_cmd()} message")

        self.payload = data[cmd_size + 1:pos]
        self._consumed = pos + 2
