Commands
========
Commands are the heart of the Inu framework. Devices on the Inu framework broadcast their Commands without a care who
hears, and devices that do care, have selective hearing and keep an eye on what is being said by devices they've been
instructed to listen to.

Each "action" device will listen to other devices, and if one of those devices issues a command, the action device will
take action. The most common of commands is the _Trigger_. The Trigger is saying "I've activated", it could be a sensor
tripping, a button being pressed or even a more complex action. Most actions will be taken from a Trigger.

Trigger Command
---------------
A Trigger command indicates something has happened, and an action should now be taken. Every Trigger includes an
integer `code` which allows the listening device to device what _kind_ of action to be taken.

The default and most common `code` is `0`. This indicates a generic trigger. For example, a PIR motion sensor that
detects motion would simply broadcast a Trigger with `code` `0`.

A more complex scenario could be a button, or a device with multiple buttons and each button could broadcast a
different `code`. The listen device might act in different ways for different `codes`. A good example of this is the
default `Relay` application, which will act like so for different codes:

* `0`: Toggle relay state (or initiate the time-delay sequence)
* `1`: Activate the relay
* `2`: Deactivate the relay

### Special Trigger Codes

While each device might behave in its own special way for different codes, there are "standard" codes that are built
into the core of the `InuApp` which will define special logic:

* `100`: INTERRUPT signal (typically used in robotics)
* `110`: Toggle device ENABLE state (an on/off toggle for the listen device)
* `111`: Enable the device
* `112`: Disable the device

Jog Command
-----------
The Jog command is designed for robotics devices that might need manual adjustments. The Jog command includes a device
ID and a set of `MOVE` arguments to jog an actuator or mechanical device a short distance.

Robotics devices will only listen to Jog commands when the device is NOT enabled and will only listen on the devices
own `central` subject. This ensures:

* Jogging must be a manual action, not initiated by automation (intended for calibration & maintenance)
* The device cannot jog while it is able to receive triggers that will activate a sequence
