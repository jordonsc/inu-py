import asyncio
from argparse import Namespace


class Utility:
    def __init__(self, args: Namespace):
        self.args = args
        self.exit_code = 0

    async def run(self):
        pass

    async def run_safe(self):
        try:
            await self.run()
        except asyncio.CancelledError:
            pass
