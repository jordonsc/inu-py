Inu-Py
======
Python implementation of the Inu framework.

The Inu framework is a set of communication protocols and applications for microcontrollers. The creates a closed
network with self-contained communication, logging & alerting for automation systems including sensors & robotics.

* [Device Communication](docs/Device_Communication.md)
  * [Commands](docs/Commands.md)
* [Hardware](docs/Hardware.md)
* [Configuration](docs/Config.md)

MicroNats
=========
The Inu framework uses NATS as its core, however as the microcontrollers are running MicroPython with a limited
Python implementation, a custom NATS API has been created specifically for MicroPython.

MicroNats is a JetStream-capable NATS client designed for MicroPython. While in its early stages this remains part of
this project, however it is a stand-alone library capable of being used by itself and will eventually be split out of
this project.

See the [MicroNats README](src/micro_nats/README.md) for more.

Inu CLI
=======
The `inu` CLI offers a range of utilities for working with the Inu environment.

    ./inu --help

Key commands from the `inu` CLI are:

### Monitor

    ./inu monitor

Starts a network monitor, displaying logs, alerts and optionly even heartbeats.

### Settings

    ./inu settings --help

Allows you to view or edit settings for every device on the network. Device settings are stream-based, so clients
should update settings as you edit them.

### Bootstrap

    ./inu bootstrap

Builds all required NATS streams, or updates them if configuration has changed (volatile!).


Bootstrapping
-------------
Bootstrapping will connect to the NATS server and create, if they don't exist, required Inu framework streams.

    ./inu bootstrap

Be warned that this may be destructive. If a stream has configuration changes that cannot be updated, the bootstrap will
_delete_ the stream and recreate it.

Dev
===
Pre-reqs
--------
Python3 with pip requirements -

    pip install -r requirements.txt

Run a local NATS server -

    podman run --name nats --rm -p 4222:4222 -p 8222:8222 --volume nats:/usr/share/nats nats --jetstream --store_dir /usr/share/nats

OSX Certificates (_OSX Only_) -

     /Applications/Python\ 3.10/Install\ Certificates.command

Testing
=======
Integration tests require a NATS server running locally.

    ./test

