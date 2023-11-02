import asyncio
import json
import logging
import struct

import urequests as requests

import machine
from inu import InuHandler, Inu, const, Status
from inu.const import LogLevel
from inu.schema.command import Ota, Trigger, Reboot
from micro_nats import model
from micro_nats.error import NotFoundError
from micro_nats.jetstream.protocol import consumer
from micro_nats.util import Time
from wifi import Wifi, error as wifi_err


class InuApp(InuHandler):
    OTA_VERSION_URL = "https://storage.googleapis.com/inu-ota/{app}/version"
    OTA_BUILD_URL = "https://storage.googleapis.com/inu-ota/{app}/build-{version}.ota"

    def __init__(self, settings_class: type):
        self.config = {}
        self.wifi = Wifi()
        self.load_config()
        self.listen_device_consumers = []

        # Set to false during device maintenance (such as an OTA update)
        self.allow_app_tick = True

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
        await self.inu.log(f"ONLINE // Inu build {const.INU_BUILD} at {ifcfg.ip}")

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
            await asyncio.sleep(1)
            machine.reset()

        await self.app_init()

        while True:
            if not self.wifi.is_connected():
                self.wifi.connect()
                await self.wifi.wait_for_connect()

            if self.allow_app_tick:
                try:
                    await self.app_tick()
                except Exception as e:
                    await self.inu.log(f"Application error - {type(e).__name__}: {e}")
                    await asyncio.sleep(1)

            await asyncio.sleep(0.01)

    async def app_tick(self):
        """
        Override this with your application-specific logic. Called inside main_loop().
        """
        pass

    async def parse_trigger_code(self, code: int):
        """
        Appropriately process a trigger message for the given code.

        This will execute special logic for the special codes (const.TriggerCode codes). Will pass on to `on_trigger()`
        if the code is non-special
        """
        if code == const.TriggerCode.INTERRUPT:
            await self.on_interrupt()
        elif code == const.TriggerCode.ENABLE_TOGGLE:
            await self.inu.status(enabled=not self.inu.state.enabled, status="")
            await self.on_enabled_changed(self.inu.state.enabled)
        elif code == const.TriggerCode.ENABLE_ON:
            if not self.inu.state.enabled:
                await self.inu.activate()
                await self.on_enabled_changed(True)
        elif code == const.TriggerCode.ENABLE_OFF:
            if self.inu.state.enabled:
                await self.inu.deactivate()
                await self.on_enabled_changed(False)
        else:
            # Normal triggers can only execute when enabled
            if self.inu.state.enabled:
                await self.on_trigger(code)
            else:
                await self.inu.log("Ignoring trigger while disabled")

    async def on_settings_updated(self):
        """
        Settings updated. Override to update anything with new settings.

        IMPORTANT: be sure to call super() as this will subscribe to listen-devices.
        """
        # Purge any existing listen device consumers
        for cons_name in self.listen_device_consumers:
            try:
                await self.inu.js.consumer.delete(const.Streams.COMMAND, cons_name)
            except NotFoundError:
                pass

        # Create a new subject listener (subjects may have changed with settings)
        async def on_subject_trigger(msg: model.Message):
            await self.inu.js.msg.ack(msg)

            try:
                trg = Trigger(msg.get_payload())
                code = int(trg.code)
            except Exception as e:
                await self.inu.log(f"Malformed trigger payload: {type(e).__name__}: {e}", LogLevel.ERROR)
                return

            self.logger.info(f"Trigger from {msg.subject}: code {code}")
            await self.parse_trigger_code(code)

        # Even if we don't have listen subjects, listen to your own "central" address
        if not hasattr(self.inu.settings, 'listen_subjects'):
            subjects = [self.inu.get_central_id()]
        else:
            subjects = self.inu.settings.listen_subjects.split(" ")
            subjects.append(self.inu.get_central_id())

        # Create consumers for all subjects
        for subject in subjects:
            if not subject.strip():
                continue

            cons = await self.inu.js.consumer.create(
                consumer.Consumer(
                    const.Streams.COMMAND,
                    consumer_cfg=consumer.ConsumerConfig(
                        filter_subject=const.Subjects.fqs(
                            [const.Subjects.COMMAND, const.Subjects.COMMAND_TRIGGER],
                            subject
                        ),
                        deliver_policy=consumer.ConsumerConfig.DeliverPolicy.NEW,
                        ack_wait=Time.sec_to_nano(1),
                    )
                ), push_callback=on_subject_trigger,
            )
            self.listen_device_consumers.append(cons.name)

        # Consumer for OTA updates
        cons = await self.inu.js.consumer.create(
            consumer.Consumer(
                const.Streams.COMMAND,
                consumer_cfg=consumer.ConsumerConfig(
                    filter_subject=const.Subjects.fqs(
                        [const.Subjects.COMMAND, const.Subjects.COMMAND_OTA],
                        self.inu.get_central_id()
                    ),
                    deliver_policy=consumer.ConsumerConfig.DeliverPolicy.NEW,
                    ack_wait=Time.sec_to_nano(1),
                )
            ), push_callback=self.on_ota,
        )
        self.listen_device_consumers.append(cons.name)

        # Consumer for reboot requests
        cons = await self.inu.js.consumer.create(
            consumer.Consumer(
                const.Streams.COMMAND,
                consumer_cfg=consumer.ConsumerConfig(
                    filter_subject=const.Subjects.fqs(
                        [const.Subjects.COMMAND, const.Subjects.COMMAND_REBOOT],
                        self.inu.get_central_id()
                    ),
                    deliver_policy=consumer.ConsumerConfig.DeliverPolicy.NEW,
                    ack_wait=Time.sec_to_nano(1),
                )
            ), push_callback=self.on_reboot,
        )
        self.listen_device_consumers.append(cons.name)

    async def on_trigger(self, code: int):
        """
        Called when a listen-device publishes a `trigger` message.

        Special codes (such as enabled, interrupt) are filtered out.
        """
        pass

    async def on_interrupt(self):
        """
        A listen-device has published an interrupt code.
        """
        pass

    async def on_ota(self, msg: model.Message):
        """
        Received an OTA message on our central address.
        """
        try:
            ota = Ota(msg.get_payload())
        except Exception as e:
            await self.inu.js.msg.term(msg)
            await self.inu.log(f"Malformed OTA payload: {type(e).__name__}: {e}", LogLevel.ERROR)
            return

        await self.inu.js.msg.ack(msg)
        await self.perform_ota_update(int(ota.version))

    async def on_reboot(self, msg: model.Message):
        """
        Received a reboot request.
        """
        try:
            Reboot(msg.get_payload())
        except Exception as e:
            await self.inu.js.msg.term(msg)
            await self.inu.log(f"Malformed reboot payload: {type(e).__name__}: {e}", LogLevel.ERROR)
            return

        await self.inu.js.msg.ack(msg)
        self.allow_app_tick = False

        await self.inu.log(f"Performing reboot by external request", LogLevel.WARNING)
        await self.inu.status(status="Performing reboot")
        await asyncio.sleep(0.5)
        machine.reset()

    async def on_enabled_changed(self, enabled: bool):
        """
        Device enabled status was changed by a listen-device.
        """
        pass

    async def on_disconnect(self):
        """
        Disconnected with NATS server.

        Clear up consumer cache.
        """
        self.listen_device_consumers = []

    async def perform_ota_update(self, version: int):
        """
        Halts operations and downloads the specified OTA update before writing to the system.

        If version is 0, the device will query for the latest version and use that.
        """
        if not self.allow_app_tick:
            await self.inu.log(f"Ignoring OTA request while device is in maintenance mode")
            return

        # Wait for device to finish whatever its doing first
        if self.inu.state.active:
            await self.inu.log("OTA update requested, will initiate when idle")
            while self.inu.state.active:
                await asyncio.sleep(0.1)

        original_state = Status(
            enabled=self.inu.state.enabled,
            active=self.inu.state.active,
            status=self.inu.state.status
        )
        self.allow_app_tick = False

        await self.inu.log(f"Applying OTA update for {self.inu.app_name} v{version}")
        await self.inu.status(enabled=False, active=False, status="Applying OTA update")
        await asyncio.sleep(0.25)  # allow messages to go out

        try:
            # Version 0 means use the latest version, grab the latest from GCP -
            if version == 0:
                response = requests.get(url=self.OTA_VERSION_URL.format(app=self.inu.app_name))
                if response.status_code != 200:
                    await self.inu.log(f"Error getting latest app version: {response.status_code}", LogLevel.ERROR)
                    await self.abort_ota(original_state)
                    return
                version = int(response.text)
                if version <= 0:
                    await self.inu.log(f"Malformed latest version: {version}", LogLevel.ERROR)
                    await self.abort_ota(original_state)
                    return
                await self.inu.log(f"Latest version for {self.inu.app_name} determined to be {version}")

            # Download OTA package into memory (should be ~ 250kb)
            # TODO: this needs a checksum validation
            response = requests.get(url=self.OTA_BUILD_URL.format(app=self.inu.app_name, version=version))
            if response.status_code != 200:
                await self.inu.log(f"Error downloading OTA package: {response.status_code}", LogLevel.ERROR)
                await self.abort_ota(original_state)
                return

        except Exception as e:
            await self.inu.log(f"OTA error - {type(e).__name__}: {e}", LogLevel.ERROR)
            await self.abort_ota(original_state)
            return

        # BE CAREFUL moving around the response content, don't duplicate the memory profile
        index = 0
        package_version = struct.unpack("<I", response.content[index:index + 4])[0]
        self.logger.info(f"OTA package version: {package_version}")
        if package_version != version:
            await self.inu.log(f"OTA package version error: expected {version}, got {package_version}", LogLevel.ERROR)
            await self.abort_ota(original_state)
            return

        index += 4

        def unpack_file():
            nonlocal index, response

            # Unpack filename
            fn_len = struct.unpack("<H", response.content[index:index + 2])[0]
            index += 2
            fn = response.content[index:index + fn_len].decode()
            index += fn_len

            data_len = struct.unpack("<I", response.content[index:index + 4])[0]
            index += 4

            self.logger.info(f"OTA write: {fn} ({data_len} b)")

            with open(fn, "wb") as fp:
                fp.write(response.content[index:index + data_len])

            index += data_len

        try:
            while index < len(response.content):
                unpack_file()
        except Exception as e:
            await self.inu.log(
                f"Error during OTA application - {type(e).__name__}: {e}; index: {index}",
                LogLevel.FATAL
            )
            await self.abort_ota(original_state)
            return

        self.inu.state = original_state
        await self.inu.status(status="OTA reboot")

        await self.inu.log(f"OTA update applied, rebooting")
        await asyncio.sleep(0.5)
        machine.reset()

    async def abort_ota(self, state: Status):
        """
        Resets the device state after an error early in the OTA process.
        """
        await self.inu.log("OTA update aborting, resuming device activity")
        self.inu.state = state
        await self.inu.status(status="")
        self.allow_app_tick = True
