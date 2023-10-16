import json
import asyncio
import logging

from inu import Inu, InuHandler, const
from inu.schema.settings.sensors import RangeTrigger

from wifi import Wifi, error as wifi_err

logging.basicConfig(level=logging.DEBUG)


class RangeApp(InuHandler):
    def __init__(self):
        self.config = None
        self.logger = logging.getLogger('app')
        self.logger.setLevel(logging.DEBUG)

        self.inu = Inu(const.Context(
            device_id=["range", "x"],
            nats_server="nats://athena.shq.sh:4222",
            has_heartbeat=True,
            settings_class=RangeTrigger,
        ), self)

        self.wifi = Wifi()
        self.load_settings()

    def load_settings(self):
        if self.config is not None:
            return

        self.logger.debug("Loading device settings..")
        with open("settings.json") as fp:
            self.config = json.load(fp)

        if 'wifi' in self.config:
            wifi = self.config['wifi']
            if 'ssid' in wifi and 'password' in wifi:
                self.wifi.set_network(wifi['ssid'], wifi['password'])
            else:
                self.logger.error("Keys 'wifi' and/or 'password' missing from wifi configuration")
        else:
            self.logger.error("Wifi configuration missing from settings")

    async def connect_wifi(self) -> bool:
        self.wifi.connect()

        try:
            await self.wifi.wait_for_connect()
            self.logger.info("Wifi connected")
            return True
        except wifi_err.BadPassword:
            self.logger.error("Wifi password incorrect")
        except wifi_err.NoAccessPoint:
            self.logger.error(f"No access point responding to {self.wifi.ssid}")
        except wifi_err.Timeout:
            self.logger.error("Timeout connecting wifi")
        except wifi_err.WifiError as e:
            self.logger.error(f"Wifi connection error: {e}")

        return False

    async def run(self):
        print("-- INU DEVICE STARTING --")
        print(f"Device ID: {self.inu.device_id}\n")

        print("Starting wifi..")
        if not await self.connect_wifi():
            print("Wifi connection failed, exiting")
            return

        ifcfg = self.wifi.ifconfig()
        print(f"  IP:      {ifcfg.ip}")
        print(f"  Subnet:  {ifcfg.subnet}")
        print(f"  Gateway: {ifcfg.gateway}")
        print(f"  DNS:     {ifcfg.dns}")

        print(f"\nBringing up NATS on {self.inu.context.nats_server}..")
        if not await self.inu.init():
            print("NATS connection failure, exiting")
            return

        print("\nBootstrap complete\n")

        while True:
            await asyncio.sleep(1)

    async def on_settings_updated(self):
        print("Settings updated")


if __name__ == "__main__":
    app = RangeApp()
    asyncio.run(app.run())
