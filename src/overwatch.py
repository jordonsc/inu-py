#!/usr/bin/env python3

import argparse
import asyncio
import logging
from signal import SIGINT, SIGTERM

from overwatch import Overwatch

parser = argparse.ArgumentParser(description='Inu Overwatch')

parser.add_argument('-v', '--verbose', dest='verbose', action='store_true',
                    help='increase logging verbosity')

parser.add_argument('-q', '--quiet', dest='quiet', action='store_true',
                    help='decrease logging verbosity')

parser.add_argument('-c', '--config', dest='config', action='store',
                    help='path to configuration JSON',
                    default='/etc/sentry.json')


def safe_exit():
    for task in asyncio.all_tasks():
        task.cancel()


if __name__ == '__main__':
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    elif args.quiet:
        logging.basicConfig(level=logging.WARNING)
    else:
        logging.basicConfig(level=logging.INFO)

    overwatch = Overwatch(args)
    loop = asyncio.get_event_loop()
    app_task = asyncio.ensure_future(overwatch.run())

    # graceful exit on signal intercept
    for signal in [SIGINT, SIGTERM]:
        loop.add_signal_handler(signal, safe_exit)

    loop.run_until_complete(app_task)
