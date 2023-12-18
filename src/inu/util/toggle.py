import argparse
import asyncio
import logging
import random
import sys
import time

from inu import Inu, InuHandler, const, Status
from inu import error
from inu.const import Context
from inu.schema.command import Trigger
from inu.schema.settings import Settings
from inu.util import Utility
from micro_nats import model
from micro_nats.jetstream.protocol.consumer import Consumer, ConsumerConfig
from micro_nats.util import Time


class ModeToggle(Utility, InuHandler):
    class Mode:
        LOCK = 1
        UNLOCK = 2
        ENABLE = 3
        DISABLE = 4

    ICO_ENABLED = "\U0001F7E2 Enabled"
    ICO_DISABLED = "\U0001F534 DISABLED"
    ICO_LOCKED = "\U0001F534 LOCKED"
    ICO_UNLOCKED = "\U0001F7E2 Unlocked"

    def __init__(self, args: argparse.Namespace, mode):
        super().__init__(args)
        self.logger = logging.getLogger('inu.util.toggle')
        self.inu = Inu(Context(
            device_id=["toggle", f"i{random.randint(1000, 9999)}"],
            nats_server=args.nats,
            has_heartbeat=False,
            settings_class=Settings,
        ), self)
        self.mode = mode
        self.device_id = args.device_id[0]

    async def run(self):
        """
        """
        if not await self.inu.init():
            return

        status = None

        async def on_status(msg: model.Message):
            nonlocal status
            if status is None:
                status = Status(msg.get_payload())
            else:
                status = Status(msg.get_payload())
                print(f"Enabled:  {self.ICO_ENABLED if status.enabled else self.ICO_DISABLED}")
                print(f"Lock:     {self.ICO_LOCKED if status.locked else self.ICO_UNLOCKED}")
                print(f"Status:   {status.status}")

        await self.inu.js.consumer.create(
            Consumer(const.Streams.STATUS, ConsumerConfig(
                filter_subject=const.Subjects.fqs(const.Subjects.STATUS, self.device_id),
                deliver_policy=ConsumerConfig.DeliverPolicy.LAST,
                ack_wait=Time.sec_to_nano(1.5),
            )), on_status,
        )

        # Wait for last known state
        start = time.monotonic()
        while status is None:
            if time.monotonic() - start > 1:
                self.logger.warning("No last known state")
                break

            await asyncio.sleep(0.01)

        payload = Trigger()
        if self.mode == self.Mode.LOCK:
            if isinstance(status, Status) and status.locked:
                print("Device already locked")
                sys.exit(2)
            payload.code = const.TriggerCode.LOCK_ON
        elif self.mode == self.Mode.UNLOCK:
            if isinstance(status, Status) and not status.locked:
                print("Device already unlocked")
                sys.exit(2)
            payload.code = const.TriggerCode.LOCK_OFF
        elif self.mode == self.Mode.ENABLE:
            if isinstance(status, Status) and status.enabled:
                print("Device already enabled")
                sys.exit(2)
            payload.code = const.TriggerCode.ENABLE_ON
        elif self.mode == self.Mode.DISABLE:
            if isinstance(status, Status) and not status.enabled:
                print("Device already disabled")
                sys.exit(2)
            payload.code = const.TriggerCode.ENABLE_OFF
        else:
            raise error.BadRequest(f"Bad toggle mode: {self.mode}")

        try:
            status = False
            self.logger.info(f"Sending status command to {self.device_id}..")
            await self.inu.nats.publish(
                const.Subjects.fqs(
                    [const.Subjects.COMMAND, const.Subjects.COMMAND_TRIGGER],
                    f"central.{self.device_id}"
                ),
                payload.marshal()
            )
        except Exception as e:
            self.logger.error(f"Publish error: {type(e).__name__}: {str(e)}")

        # Wait for status reply
        start = time.monotonic()
        while status is False:
            if time.monotonic() - start > 3:
                self.logger.error("Timeout waiting for device update")
                break

            await asyncio.sleep(0.01)
