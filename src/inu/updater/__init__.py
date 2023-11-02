import asyncio
import binascii
import logging
import os
import struct
import time

import machine
import urequests as requests
from inu import Status
from inu.const import LogLevel


class Updater:
    async def perform_update(self, version: int):
        pass


class OtaUpdater(Updater):
    OTA_VERSION_URL = "https://storage.googleapis.com/inu-ota/{app}/version?v={v}"
    OTA_BUILD_URL = "https://storage.googleapis.com/inu-ota/{app}/build-{version}.ota?v={v}"
    OTA_CHECKSUM_URL = "https://storage.googleapis.com/inu-ota/{app}/build-{version}.checksum?v={v}"

    MAX_RETRIES = 10

    def __init__(self, app):
        from inu.app import InuApp
        self.app: InuApp = app
        self.logger = logging.getLogger("inu.ota")

    async def perform_update(self, version: int):
        """
        Halts operations and downloads the specified OTA update before writing to the system.

        If version is 0, the device will query for the latest version and use that.
        """
        if not self.app.allow_app_tick:
            await self.app.inu.log(f"Ignoring OTA request while device is in maintenance mode")
            return

        # Wait for device to finish whatever its doing first
        if self.app.inu.state.active:
            await self.app.inu.log("OTA update requested, will initiate when idle")
            while self.app.inu.state.active:
                await asyncio.sleep(0.1)

        original_state = Status(
            enabled=self.app.inu.state.enabled,
            active=self.app.inu.state.active,
            status=self.app.inu.state.status
        )
        self.app.allow_app_tick = False

        await self.app.inu.log(f"Applying OTA update for {self.app.inu.app_name} v{version}")
        await self.app.inu.status(enabled=False, active=False, status="Applying OTA update")
        await asyncio.sleep(0.25)  # allow messages to go out

        # NB: INTENTIONALLY NOT MODULARISING to avoid increasing memory footprint
        try:
            # Cache-busting
            v = time.time()

            # Version 0 means use the latest version, grab the latest from GCP -
            if version == 0:
                version = await self.get_latest_version()
                if version <= 0:
                    await self.app.inu.log(f"Error acquiring latest version ({version})", LogLevel.ERROR)
                    await self.abort_update(original_state)
                    return
                await self.app.inu.log(f"Latest version for {self.app.inu.app_name} determined to be {version}")

            # This is prone to a high error rate, set a retry-loop -
            response = None
            err = None
            for i in range(0, self.MAX_RETRIES):
                # Check checksum of OTA package
                self.logger.info("Getting OTA packet checksum..")
                response = requests.get(
                    url=self.OTA_CHECKSUM_URL.format(app=self.app.inu.app_name, version=version, v=v)
                )
                if response.status_code != 200:
                    err = f"Error downloading OTA checksum: {response.status_code}"
                    self.logger.warning(err)
                    continue
                checksum = response.text

                await asyncio.sleep(0)

                # Download OTA package into memory (should be ~ 250kb)
                self.logger.info("Downloading OTA packet..")
                response = requests.get(
                    url=self.OTA_BUILD_URL.format(app=self.app.inu.app_name, version=version, v=v)
                )
                if response.status_code != 200:
                    err = f"Error downloading OTA package: {response.status_code}"
                    self.logger.warning(err)
                    continue

                await asyncio.sleep(0)

                # Validate checksum
                self.logger.info(f"Validating checksum ({len(response.content)} bytes)..")
                ota_checksum = "%08X" % (binascii.crc32(response.content) & 0xFFFFFFFF)
                if ota_checksum != checksum:
                    err = f"OTA checksum mismatch; expected: {checksum}, got: {ota_checksum}"
                    self.logger.warning(err)
                    continue

                err = None
                break

            if isinstance(err, str):
                await self.app.inu.log(err, LogLevel.ERROR)
                await self.abort_update(original_state)
                return

        except Exception as e:
            await self.app.inu.log(f"OTA error - {type(e).__name__}: {e}", LogLevel.ERROR)
            await self.abort_update(original_state)
            return

        await asyncio.sleep(0)

        # BE CAREFUL moving around the response content, don't duplicate the memory profile
        index = 0
        package_version = struct.unpack("<I", response.content[index:index + 4])[0]
        self.logger.info(f"OTA package version: {package_version}")
        if package_version != version:
            await self.app.inu.log(
                f"OTA package version error: expected {version}, got {package_version}", LogLevel.ERROR
            )
            await self.abort_update(original_state)
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

            self.logger.info(f"write: {fn} ({data_len} b)")
            self.makedirs(fn)

            with open(fn, "wb") as fp:
                fp.write(response.content[index:index + data_len])

            index += data_len

        try:
            while index < len(response.content):
                unpack_file()
                await asyncio.sleep(0)
        except Exception as e:
            await self.app.inu.log(
                f"Error during OTA application - {type(e).__name__}: {e}; index: {index}",
                LogLevel.FATAL
            )
            await self.abort_update(original_state)
            return

        self.app.inu.state = original_state
        await self.app.inu.status(status="OTA reboot")

        await self.app.inu.log(f"OTA update applied, rebooting")
        await asyncio.sleep(0.5)
        machine.reset()

    @staticmethod
    def makedirs(fn: str):
        """
        Creates all directories for a given filename.
        """
        paths = fn.split("/")
        paths.pop()
        path = ""
        for p in paths:
            path += f"/{p}"
            try:
                os.mkdir(path)
            except OSError:
                # exists
                pass

    async def get_latest_version(self):
        """
        Hit the VERSION URL to determine the latest build for the current app.
        """
        response = requests.get(url=self.OTA_VERSION_URL.format(app=self.app.inu.app_name, v=time.time()))
        if response.status_code != 200:
            return -1

        return int(response.text)

    async def abort_update(self, state: Status):
        """
        Resets the device state after an error early in the OTA process.
        """
        await self.app.inu.log("OTA update aborting, resuming device activity")
        self.app.inu.state = state
        await self.app.inu.status(status="")
        self.app.allow_app_tick = True
