try:
    import network
except ImportError:
    pass

import logging
import time
import asyncio

from . import error as wifi_err


class Status:
    IDLE = 0
    CONNECTING = 10
    CONNECTED = 11

    NO_AP = 20
    BAD_PASSWORD = 21
    ASSOC_FAIL = 22
    BEACON_TIMEOUT = 22
    HANDSHAKE_TIMEOUT = 23

    ERR_UNKNOWN = 30

    @classmethod
    def is_error(cls, status: int):
        return status >= 20

    @classmethod
    def from_wlan(cls, status):
        if status == 1000:
            return Status.IDLE
        elif status == 1001:
            return Status.CONNECTING
        elif status == 1010:
            return Status.CONNECTED
        elif status == 200:
            return Status.BEACON_TIMEOUT
        elif status == 201:
            return Status.NO_AP
        elif status == 202:
            return Status.BAD_PASSWORD
        elif status == 203:
            return Status.ASSOC_FAIL
        elif status == 204:
            return Status.HANDSHAKE_TIMEOUT
        else:
            return Status.ERR_UNKNOWN


class InterfaceConfig:
    def __init__(self, cfg: tuple):
        self.ip, self.subnet, self.gateway, self.dns = cfg


class Wifi:
    def __init__(self, ssid: str = None, pw: str = None):
        self.logger = logging.getLogger('wifi')
        self.logger.setLevel(logging.DEBUG)
        self.station = network.WLAN(network.STA_IF)
        self.station.active(True)

        self.ssid = ssid
        self.password = pw

    def set_network(self, ssid: str, pw: str):
        self.ssid = ssid
        self.password = pw

    def connect(self):
        if self.is_connected():
            return

        self.logger.info(f"Connecting to {self.ssid}..")
        self.station.connect(self.ssid, self.password)

    def disconnect(self):
        if not self.is_connected():
            return

        self.logger.info(f"Disconnecting")
        self.station.disconnect()

    def is_connected(self) -> bool:
        return self.station.isconnected()

    async def wait_for_connect(self, timeout: float = 30.0):
        start = time.time()

        while self.status() != Status.CONNECTED:
            if time.time() - start > timeout:
                raise wifi_err.Timeout()

            stat = self.status()
            if stat == Status.NO_AP:
                raise wifi_err.NoAccessPoint()
            elif stat == Status.BAD_PASSWORD:
                raise wifi_err.BadPassword()
            elif stat == Status.HANDSHAKE_TIMEOUT:
                raise wifi_err.WifiError("Handshake timeout")
            elif stat == Status.BEACON_TIMEOUT:
                raise wifi_err.WifiError("Beacon timeout")
            elif stat == Status.ASSOC_FAIL:
                raise wifi_err.WifiError("Assoc fail")
            elif stat == Status.ERR_UNKNOWN:
                raise wifi_err.WifiError("Unknown status error")

            await asyncio.sleep(0.1)

    def status(self):
        return Status.from_wlan(self.station.status())

    def ifconfig(self) -> InterfaceConfig:
        if not self.is_connected():
            raise wifi_err.NotConnected()

        return InterfaceConfig(self.station.ifconfig())

    def get_mac(self) -> bytes:
        return self.station.config('mac')

    @staticmethod
    def get_hostname():
        return network.hostname()
