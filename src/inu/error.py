class InuError(Exception):
    pass


class BadRequest(InuError):
    pass


class NoConnection(InuError):
    pass


class Malformed(InuError):
    pass


class InvalidDeviceId(InuError):
    pass


class UnsupportedDeviceType(InuError):
    pass
