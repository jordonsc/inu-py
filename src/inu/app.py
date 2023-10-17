import asyncio
import json
import logging

from inu import InuHandler, Inu, const
from wifi import Wifi, error as wifi_err


class InuApp(InuHandler):
    def __init__(self, settings_class: type):
        self.config = {}
        self.wifi = Wifi()
        self.load_config()

        log_level = self.get_config('log_level', 'INFO')
        if not hasattr(logging, log_level):
            print(f"Invalid log level: {log_level}")
            exit(1)

        logging.basicConfig(level=getattr(logging, log_level))
        self.logger = logging.getLogger('app')

        self.inu = Inu(const.Context(
            device_id=self.get_config('device_id').split('.'),
            nats_server=self.get_config(['nats', 'server']),
            has_heartbeat=self.get_config('heartbeat', True),
            settings_class=settings_class,
        ), self)

    def load_config(self):
        """
        Load the settings.json file. Should only ever be called once.
        """
        with open("settings.json") as fp:
            self.config = json.load(fp)

        if 'wifi' in self.config:
            wifi = self.config['wifi']
            if 'ssid' in wifi and 'password' in wifi:
                self.wifi.set_network(wifi['ssid'], wifi['password'])
            else:
                print("Keys 'wifi' and/or 'password' missing from wifi configuration")
        else:
            print("Wifi configuration missing from settings")

    def get_config(self, key: str | list, default=None):
        """
        Get a setting from the local config, or return the default.
        """
        if isinstance(key, list):
            path = self.config
            for subkey in key:
                if subkey not in path:
                    return default
                path = path[subkey]
            return path

        if key in self.config:
            return self.config[key]
        else:
            return default

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

    async def init(self):
        """
        Init the application. Run once before falling into `main_loop()`.
        """
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

        print("Waiting for settings..")
        while not self.inu.has_settings:
            await asyncio.sleep(0.1)

        print("\nBootstrap complete\n")
        await self.inu.log("Online")

    async def main_loop(self):
        """
        Override this with your application-specific loop.
        """
        await self.init()

        while True:
            await self.on_loop()
            await asyncio.sleep(0.1)

    async def on_loop(self):
        """
        Checkup on wifi, NATS connection, etc.
        """
        pass

    async def on_settings_updated(self):
        """
        Settings updated. Override to update anything with new settings.
        """
        pass
