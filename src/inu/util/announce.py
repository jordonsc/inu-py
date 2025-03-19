import argparse
import logging
import random

from inu import Inu, InuHandler, const
from inu.const import Context
from inu.schema import Announcement
from inu.schema.settings import Settings
from inu.util import Utility


class Announce(Utility, InuHandler):

    def __init__(self, args: argparse.Namespace):
        super().__init__(args)
        self.logger = logging.getLogger('inu.util.announce')
        
        self.inu = Inu(Context(
            device_id=["announce", f"i{random.randint(1000, 9999)}"],
            nats_server=args.nats,
            has_heartbeat=False,
            settings_class=Settings,
        ), self)

        self.chime = args.chime
        self.track = args.track
        self.message = args.message

    async def run(self):
        if not await self.inu.init():
            return

        payload = Announcement()
        payload.chime = self.chime if self.chime is not None else False
        payload.track = self.track if self.track is not None else None
        payload.message = self.message

        try:
            self.logger.info(f"Broadcasting announcement..")
            await self.inu.nats.publish(
                const.Subjects.fqs(
                    const.Subjects.COMMAND, const.Subjects.COMMAND_ANNOUNCE,
                ),
                payload.marshal()
            )
        except Exception as e:
            self.logger.error(f"Publish error: {type(e).__name__}: {str(e)}")

        self.logger.info(f"Completed.")
