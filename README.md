Inu-Py
======
Python implementation of the Inu framework.

The Inu framework is a set of communication protocols and applications for microcontrollers. The creates a closed
network with self-contained communication, logging & alerting for automation systems including sensors & robotics.

* [Device Communication](docs/Device_Communication.md)
  * [Commands](docs/Commands.md)
* [Hardware](docs/Hardware.md)
* [Supported Devices](docs/Supported_Devices.md)
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

    ./inu monitor [-l] [-a] [-c] [-s] [-b]

Starts a network monitor, displaying logs, alerts and optionally even heartbeats.

### Settings

    ./inu settings --help

Allows you to view or edit settings for every device on the network. Device settings are stream-based, so clients
should update settings as you edit them. The settings command also displays device information, heartbeats and allows
you to send commands directly to the device. 

For robotics devices, you can jog the device actuators (when in `disabled` mode only).

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
_Inu_ requires the following:
 * Python 3.10+
 * A NATS server with JetStream support
 * Grafana & Loki for observability (optional)

Install Python dependencies -

    pip install -r requirements.txt

Prep config for required services -

    mkdir /etc/grafana /etc/loki
    # copy samples from `docs/confs/`

Run Docker/Podman containers of required services:

    podman run -d --name nats --network host -v jetstream:/usr/share/nats nats:latest --jetstream --store_dir /usr/share/nats
    podman run -d --name loki --network host -v loki-data:/loki -v /etc/loki:/mnt/config grafana/loki -config.file=/mnt/config/loki-config.yaml
    podman run -d --name grafana --network host -v grafana-data:/var/lib/grafana -v /etc/grafana/grafana.ini:/etc/grafana/grafana.ini grafana/grafana-oss

    # There-on-in you can do:
    podman stop grafana loki nats
    podman start nats loki grafana

OSX Certificates (_OSX only_) -

     /Applications/Python\ 3.10/Install\ Certificates.command

Bootstrap the NATS server (_once only_) -

    ./inu bootstrap 

Running Sentry
--------------
_Inu Sentry_ is a service that monitors the streams and forwards logs to a logging and alerting services (currently 
only _Loki_ and _PagerDuty_ supported). In addition, it monitors heartbeats and raises alerts when a device no longer
beats.

    ./sentry -c docs/confs/sentry.json

Testing
=======
Integration tests require a NATS server running locally.

    ./test

