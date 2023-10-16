from micro_nats.protocol.cmd import ClientCommand
from micro_nats.util import Time


class Nak(ClientCommand):
    """
    Informs the server that you cannot process this message. The message will be resent.
    """

    @classmethod
    def get_cmd(cls) -> bytes:
        return b'-NAK'

    def __init__(self, delay: float = None):
        """
        Nack a message, delaying redelivery by `delay` seconds, if provided.
        """
        self.delay: float = Time.sec_to_nano(delay) if delay else None

    def marshal(self) -> bytes:
        if self.delay:
            return self.get_cmd() + b' {"delay":' + str(int(self.delay)).encode() + b'}\r\n'
        else:
            return self.get_cmd() + b'\r\n'


class InProgress(ClientCommand):
    """
    Informs the server that you are still working on this message. The ack-retry timer will be reset.

    Can be used multiple times on the same message.
    """

    @classmethod
    def get_cmd(cls) -> bytes:
        return b'+WPI'

    def marshal(self) -> bytes:
        return self.get_cmd()


class Term(ClientCommand):
    """
    Informs the server this message cannot be processed, and do not attempt to reprocess it.
    """

    @classmethod
    def get_cmd(cls) -> bytes:
        return b'+TERM'

    def marshal(self) -> bytes:
        return self.get_cmd()
