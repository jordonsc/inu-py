Change Log
==========
### Build 46
* 

### Build 45
* Added "WAIT" (103) and "BREAK" (104) trigger codes to reset or break the WAIT command timer
* Increased NATS default connection timeout to 30 seconds which was causing issues with subscriptions at low values

### Build 44
* Robotics `WAIT` command can now be interrupted

### Build 43
* Added `Capacitive` app for touch/water sensors
* Added `Light` for ambient light sensors
* Added `APA102` LED controller to robotics
* Robotics can now optionally accept triggers as interrupts
* Robotics `WAIT` command can now accept a time specifier: `WAIT 5s`
  * Allowed time specifiers: `s` (seconds), `m` (minutes), `h` (hours)

### Build 42
* Added `SwitchManager`, allowing other apps to include the Switch app logic
* Robotics now inherits `SwitchManager`

### Build 41
* Switch now has a built-in tolerance and the limiter tolerance is configurable

### Build 40
* `idle_power` mode is now a delay function, disabling power after a given period of time
* Increased limiter tolerance

### Build 39
* Added a tolerance in Robotics limiters to reduce false-positives from interference
* Set `idle_power` default to True

### Build 38
* Added `alert` to Robotics stepper controllers
* Added `idle power` settings to Robotics
* Removed the direct correlation between a Robotics device and its physical device's enabled states
* Changed Robotics default pin configuration to match a Tiny S3 pinout

### Build 37
* Fixed bug with devices ignoring enable/disable trigger codes

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
