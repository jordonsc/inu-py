import asyncio
import json
import logging
import machine

from inu import InuHandler, Inu, const
from micro_nats import model
from micro_nats.jetstream.protocol import consumer
from micro_nats.util import Time
from wifi import Wifi, error as wifi_err


class InuApp(InuHandler):
    INU_VERSION = "1.0.0"

    def __init__(self, settings_class: type):
        self.config = {}
        self.wifi = Wifi()
        self.load_config()
        self.listen_device_consumers = []

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
        try:
            self.wifi.connect()
        except OSError as e:
            self.logger.info(f"Wifi error: {e} -- delay retry")
            await asyncio.sleep(3)
            return False

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

    async def init(self) -> bool:
        """
        Init the application. Executed by `run()`.

        Returns false if a key init item fails.
        """
        print("-- INU DEVICE STARTING --")
        print(f"Device ID: {self.inu.device_id}\n")

        print("Starting wifi..")
        if not await self.connect_wifi():
            print("Wifi connection failed, exiting")
            return False

        ifcfg = self.wifi.ifconfig()
        print(f"  IP:      {ifcfg.ip}")
        print(f"  Subnet:  {ifcfg.subnet}")
        print(f"  Gateway: {ifcfg.gateway}")
        print(f"  DNS:     {ifcfg.dns}")

        print(f"\nBringing up NATS on {self.inu.context.nats_server}..")
        if not await self.inu.init():
            print("NATS connection failure, exiting")
            return False

        print("Waiting for settings..")
        while not self.inu.has_settings:
            await asyncio.sleep(0.1)

        print("\nBootstrap complete\n")
        await self.inu.status(enabled=True, active=False)
        await self.inu.log(f"ONLINE // Inu v{self.INU_VERSION} at {ifcfg.ip}")

        return True

    async def app_init(self):
        """
        Called once when the device boots. Override.
        """
        pass

    async def run(self):
        """
        Indefinite app loop.

        Checkup on wifi, NATS connection, etc. Will call `app_tick()` inside the main loop.
        """
        if not await self.init():
            self.logger.error("Init failed. Rebooting.")
            await asyncio.sleep(1000)
            machine.reset()

        await self.app_init()

        while True:
            if not self.wifi.is_connected():
                self.wifi.connect()
                await self.wifi.wait_for_connect()

            await self.app_tick()
            await asyncio.sleep(0.01)

    async def app_tick(self):
        """
        Override this with your application-specific logic. Called inside main_loop().
        """
        pass

    async def on_settings_updated(self):
        """
        Settings updated. Override to update anything with new settings.

        IMPORTANT: be sure to call super() as this will subscribe to listen-devices.
        """
        if not hasattr(self.inu.settings, 'listen_subjects'):
            return

        # Purge any existing listen device consumers
        for cons_name in self.listen_device_consumers:
            await self.inu.js.consumer.delete(const.Streams.COMMAND, cons_name)

        async def on_subject_trigger(msg: model.Message):
            await self.inu.js.msg.ack(msg)

            try:
                data = json.loads(msg.get_payload())
                code = int(data['code'])
            except Exception as e:
                self.logger.warning(f"Malformed trigger payload: {type(e)}: {e}")
                code = 0

            self.logger.info(f"Trigger from {msg.subject}: code {code}")
            await self.on_trigger(code)

        subjects = self.inu.settings.listen_subjects.split(" ")

        # Create consumers for all subjects
        for subject in subjects:
            cons = await self.inu.js.consumer.create(
                consumer.Consumer(
                    const.Streams.COMMAND,
                    consumer_cfg=consumer.ConsumerConfig(
                        filter_subject=const.Subjects.fqs(
                            [const.Subjects.COMMAND, const.Subjects.COMMAND_TRIGGER],
                            subject
                        ),
                        deliver_policy=consumer.ConsumerConfig.DeliverPolicy.NEW,
                        ack_wait=Time.sec_to_nano(3),
                    )
                ), push_callback=on_subject_trigger,
            )
            self.listen_device_consumers.append(cons.name)

    async def on_trigger(self, code: int):
        """
        Called when a listen-device publishes a `trigger` message.
        """
        pass

    async def on_disconnect(self):
        """
        Disconnected with NATS server.

        Clear up consumer cache.
        """
        self.listen_device_consumers = []
