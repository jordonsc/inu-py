Inu Net Bundles Devices
=======================

Action Devices
--------------
Action Devices are devices that make something happen. That might be activate some lights, or move an actuator. They
would typically respond to a trigger device, like a sensor.

### Robotics
_Robotics_ is a generalised control device capable of running scripts that control physical devices. Typical devices
that Robotics would control are stepper motors, servos, lights, etc.

> LED strips would typically be controlled via Robotics.

### Relay
_Relay_ is a simple on/off switch, it controls the power to a connected electrical circuit and allows for time-delay
switching. You can control lighting with a Relay device, however you can only turn it off/on - you cannot dim it.


Trigger Devices
---------------
Trigger Devices are devices that detect something happening. That might be a PIR sensor, ambient light, laser-trip or
a button press.

### Capacitive
The _Capacitive_ application watches a capacitive sensor, typically a touch sensor but could also be used for a water
sensor or similar.

### Motion
The _Motion_ application watches a PIR sensor, detecting motion in a room.

### Light
The _Light_ application watches a light sensor, detecting ambient light levels.

### Switch
The _Switch_ application listens for a series of physical buttons, typically a momentary switch.

> NPN sensors, such as a laser-trip or pressure-pad sensor, would typically be controlled via Switch.

### Range
_Range_ devices are distance ranging sensors, typically used for detecting objects in front of a device. Typical
implementations would be a laser ranging device or ultrasonic sensor. These are much better suited for outdoors use
compared to PIR sensors.
