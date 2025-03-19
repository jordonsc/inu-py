import argparse
import logging
import random

from inu import Inu, InuHandler, const
from inu.const import Context
from inu.schema import Alarm as AlarmSchema
from inu.schema.settings import Settings
from inu.util import Utility


class Alarm(Utility, InuHandler):

    def __init__(self, args: argparse.Namespace):
        super().__init__(args)
        self.logger = logging.getLogger('inu.util.alarm')
        
        self.inu = Inu(Context(
            device_id=["alarm", f"i{random.randint(1000, 9999)}"],
            nats_server=args.nats,
            has_heartbeat=False,
            settings_class=Settings,
        ), self)

        self.track = args.track
        self.cause = args.cause
        self.active = args.active

    async def run(self):
        if not await self.inu.init():
            return

        payload = AlarmSchema()
        payload.active = self.active if self.active is not None else False
        payload.track = self.track if self.track is not None else None
        payload.cause = self.cause

        try:
            if self.active:
                self.logger.info(f"Raising alarm, cause: {self.cause if self.cause is not None else '(no cause)'}")
            else:
                self.logger.info(f"Standing down alarm")

            await self.inu.nats.publish(
                const.Subjects.fqs(
                    const.Subjects.COMMAND, const.Subjects.COMMAND_ALARM,
                ),
                payload.marshal()
            )
        except Exception as e:
            self.logger.error(f"Publish error: {type(e).__name__}: {str(e)}")

        self.logger.info(f"Completed.")
