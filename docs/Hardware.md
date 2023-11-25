Preparing ESP32 Boards
======================
To install applications on an ESP32 board, you need to prepare _MicroPython_ along with some dependencies.

Install MicroPython
-------------------
Grab the latest version of MicroPython from the website, download the `.bin` file (not `.uf2`) -
* [TinyS2](https://micropython.org/download/UM_TINYS2/)
* [TinyS3](https://micropython.org/download/UM_TINYS3/)

Install `esptool` locally to push MicroPython to the device, and `mpremote` to upload/manage it:

    pip install esptool mpremote

To put your device into bootloader mode, hold the `BOOT` button and press the `RESET` button once. You can now use
`esptool` to send the new firmware to the device.

> NB: the chip "esp32s2" and port "ttyACM0" may differ from your configuration - update these with the correct values.

Erase any existing bootloader:

    # TinyS2:
    esptool.py --chip esp32s2 --port /dev/ttyACM0 erase_flash

    # TinyS3:
    esptool.py --chip esp32s3 --port /dev/ttyACM0 erase_flash

And load in the `.bin` file you downloaded above:

    # TinyS2:
    esptool.py --chip esp32s2 --port /dev/ttyACM0 write_flash -z 0x1000 /path/to/firmware.bin

    # TinyS3:
    esptool.py --chip esp32s3 --port /dev/ttyACM0 write_flash -z 0x0 /path/to/firmware.bin

MicroPython 101
---------------
_MicroPython_ works by installing a _CPython_ based program on the ESP32 device, then creating a storage device allowing
you to copy files that will be executed by _MicroPyton_.

When the device is started, it executes `boot.py` to bootstrap anything, followed by `main.py` as your Python 
application's entry-point.

You can use the `repl` interface to execute Python code remotely, monitor `stdout` or perform a soft-reboot.

    mpremote a0 repl

> Bear in mind that _MicroPython_ only implements a subset of the CPython definition, so you won't have access to 
> complex libraries.

See also: [MicroPython Libraries](https://github.com/micropython/micropython-lib)

Serial Connection
-----------------
You can manage the device with the `mpremote` tool, this will allow you to copy files, run programs and use the `repl`
interface of the device.

> NB: `a0` is an alias for `/dev/ttyACM0`

    # List all files on the device:
    mpremote a0 ls

    # Mount a local directory (`.`) to the device, then run a program (runs off local filesystem):
    mpremote a0 mount . run foo.py
