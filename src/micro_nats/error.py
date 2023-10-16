class MicroNatsError(Exception):
    """
    Base MicroNats exception. All exceptions should derive this.
    """
    pass


"""
Generic errors.
"""


class Malformed(MicroNatsError):
    pass


class UnexpectedValue(MicroNatsError):
    pass


class NoConnectionError(MicroNatsError):
    pass


class ConnectionRefused(MicroNatsError):
    pass


class RequestRefused(MicroNatsError):
    pass


class NetworkTimeout(MicroNatsError):
    pass


class NotFoundError(MicroNatsError):
    pass


class AlreadyExistsError(MicroNatsError):
    pass


class NotSupported(MicroNatsError):
    pass


"""
Protocol errors are concerned with parsing packets inbound from the server.
"""


class ProtocolError(MicroNatsError):
    pass


class ParseError(ProtocolError):
    pass


class IncompletePayload(ProtocolError):
    pass
