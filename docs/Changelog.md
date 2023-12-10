Change Log
==========
### Build 36
* Range devices now have min-range

### Build 35
* Removing the disabled-wait logic in Robotics
* Actuator has a ramp-up time instead of trying to move at full-speed instantly

### Build 34
* Allow device priority of P5
* P5 priority does not page (log-only)
* Improved error handling when subscribing to listen devices

### Build 33
* Relay 'state' log level changed to debug

### Build 32
* Monitor no longer has a heartbeat
* Fixed status issue in Relay
* Added experimental Robotics disabled-safe-wait logic

### Build 31
* Relay doesn't log state change when it's not actually changing state
* Added Sentry, supporting Loki & PagerDuty
* Added `device_priority` to all device settings which influences Sentry alert priority
* Motion & Range sensors can now be locked/disabled

### Build 30
* Relay device now logs status change

### Build 29
* Added `Locked` to device status which will inhibit device action

### Build 28
* Added interrupt paths to robotics
* Robotics now calibrate via settings, not hardware config
* Switches can now repeat triggers when continuously active
* Switches no longer have an unused cooldown time
* Device will reboot on uncaught exception or wifi issues

### Build 27
* Added Switch application
* Devices now assume their last state (except Robotics, which has more complex logic)

### Build 26
* Heartbeat now includes build number & local address
