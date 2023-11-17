Known Issues
============

All Devices
-----------
### OTA
You can send multiple OTA requests when the device is active, that will run concurrently when device becomes idle.

Robotics
--------
### Actuator Overrun
Could potentially overrun if wifi drops during actuator MV operation (consuming too much time during reconnect).
