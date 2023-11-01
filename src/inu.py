#!/usr/bin/env python3

import asyncio
import logging
import argparse
from signal import SIGINT, SIGTERM

from inu.util import Utility
from inu.util.monitor import Monitor
from inu.util.bootstrap import Bootstrap
from inu.util.settings import Settings
from inu.util.build import Build

from textual.app import App as TuiApp

parser = argparse.ArgumentParser(description='Inu Framework Command Line Tool')

parser.add_argument('-v', '--verbose', dest='verbose', action='store_true',
                    help='increase logging verbosity')

parser.add_argument('-q', '--quiet', dest='quiet', action='store_true',
                    help='decrease logging verbosity')

parser.add_argument('-n', '--nats', dest='nats', action='store',
                    help='nats server address; defaults to nats://127.0.0.1:4222',
                    default='nats://127.0.0.1:4222')

subparsers = parser.add_subparsers(dest="cmd")

# Stream bootstrapper
bootstrap_parser = subparsers.add_parser('bootstrap', help='bootstrap all streams')
bootstrap_parser.add_argument('-c', '--clean', dest="clean", action='store_true',
                              help="delete consumers/streams and rebuild")
bootstrap_parser.add_argument('-x', '--delete', dest="delete", action='store_true',
                              help="clean only, do not recreate (implies -c)")

# Network monitor
monitor_parser = subparsers.add_parser('monitor', help='monitor logs & alerts')
monitor_parser.add_argument('-l', '--logs', dest="logs", action='store_true',
                            help="includes logs in stream; defaults to -l if no other options are provided")
monitor_parser.add_argument('-a', '--alerts', dest="alerts", action='store_true',
                            help="includes alerts in stream")
monitor_parser.add_argument('-b', '--heartbeats', dest="heartbeats", action='store_true',
                            help="includes heartbeats in stream")
monitor_parser.add_argument('-c', '--commands', dest="commands", action='store_true',
                            help="includes commands in stream")
monitor_parser.add_argument('-s', '--settings', dest="settings", action='store_true',
                            help="includes settings changes in stream")
monitor_parser.add_argument('-t', '--time', dest="time", action='store',
                            help="time to start logs from, either relative (eg 3m20s) or absolute "
                                 "(eg 2023-04-20T10:03:10)")
monitor_parser.add_argument('-x', '--limit', dest="limit", action='store',
                            help="max number of lines to log before halting; will tail until limit reached")

# Settings config
settings_parser = subparsers.add_parser('settings', help='view or edit device settings')
settings_parser.add_argument(dest="device_id", nargs=1, help="Device unique ID, eg 'sensor.my_sensor'")

# Device builder
build_parser = subparsers.add_parser('build', help='prepare and deploy an ESP32 application')
build_parser.add_argument(dest="device_id", nargs=1, help="Device unique ID, eg 'sensor.my_sensor'")
build_parser.add_argument('-p', '--port', dest="port", action='store', help="Device port; default '/dev/ttyACM0'",
                          default="/dev/ttyACM0")
build_parser.add_argument('-l', '--local', dest="local", action='store_true',
                          help="build to the local `build/` directory instead of a remote device; overrides -p")
build_parser.add_argument('-o', '--ota', dest="ota", action='store_true',
                          help="create an OTA update; overrides -p and -l")
build_parser.add_argument('-s', '--settings', dest="settings", action='store_true',
                          help="only apply new settings to the device")


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

    app = None
    if args.cmd == "monitor":
        app = Monitor(args)
    elif args.cmd == "bootstrap":
        app = Bootstrap(args)
    elif args.cmd == "settings":
        app = Settings(args)
    elif args.cmd == "build":
        app = Build(args)
    else:
        parser.print_usage()
        exit(1)

    if isinstance(app, TuiApp):
        # Text UI - has its own asyncio bootstrap
        app.run()
        exit(0)

    elif isinstance(app, Utility):
        # Utility - native Inu asyncio app
        loop = asyncio.get_event_loop()
        app_task = asyncio.ensure_future(app.run_safe())

        # graceful exit on signal intercept
        for signal in [SIGINT, SIGTERM]:
            loop.add_signal_handler(signal, safe_exit)

        loop.run_until_complete(app_task)
        exit(app.exit_code)

    else:
        print("Unknown application type")
        exit(9)
