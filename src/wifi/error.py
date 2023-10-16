class WifiError(Exception):
    pass


class NotConnected(WifiError):
    pass


class Timeout(WifiError):
    pass


class BadPassword(WifiError):
    pass


class NoAccessPoint(WifiError):
    pass
