Configuring Devices
===================
The `inu build` command will look for JSON files in the `config/` directory, and generate a `settings.json` file for
the device being built from that. In order, it will generate the file by merging the device ID with the `base.json` and
then with every progressive path of the device ID, for example:

> given device ID: range.sonar.foo

* `{'device_id': 'range.sonar.foo', 'hostname': 'range_sonar_foo'}`
* `config/base.json`
* `config/range.json`
* `config/range.sonar.json`
* `config/range.sonar.foo.json`

It is recommended to keep the contents of the `config/` directory in a private repo or vault.


Expected Content
================
You are not restricted by content per JSON file, but an example would be do put global config in the `base.json` file
and expand upon that with the device pathline:

> base.json

    {
        "heartbeat": true,
        "log_level": "INFO",
        "nats": {
            "server": "nats://my.nats.server:4222"
        },
        "wifi": {
            "ssid": "xxxx",
            "password": "xxxx"
        }
    }

> range.json

    {
        "range": {
            "tx": 33,
            "rx": 38
        }
    }

If you have a mix of different type of "range" devices, you can use the device ID in full to specify configuration:

> range.sonar.json

    {
        "range": {
            "type": "sonar"
        }
    }
