Inu Framework Device Communication
==================================
The Inu framework uses NATS as the beating heart of it's infrastructure. All communication between devices, all logs &
alerts, are achieved via NATS JetStream streams.

Subject Structure
-----------------
Each device has a subject for each stream (see below), it typically _broadcasts_ on this subject, requiring other
devices to _listen explicitly to a known device_. However, each device also has its own "central" address, in which
it listens for specific commands on that address.

This creates a structure where by default, each device yells and anyone listening can act. However, in certain
circumstances devices will only listen to messaged directed specifically at them.

### Device IDs

Each device must have a multi-part device ID delimited by a `.` with the first section being the application type,
which is a fixed list of supported applications. The remainder of the device ID can be used for breaking down the device
type or taxonomy.

Examples:

    robotics.punching-machine
    motion.pir.hallway
    range.sonar.hallway.stairwell
    monitor.i12345

Even CLI applications (as as `monitor`) will create a temporary unique device ID.

### Device Subjects

The devices personal subject will be in the form of:

    <stream_subj>.<device_id>

eg:

    cmd.trigger.motion.pir.hallway

But in addition, the devices "central" subject (the self-listening address) will be:

    <stream_subj>.central.<device_id>

eg:

    cmd.jog.central.robotics.punching-machine
    cmd.ota.central.motion.pir.hallway

Inu Core Streams
----------------
A JetStream server must be initialised with the core streams required for all devices to operate. These are found in
`inu/const.py`:

* `logs` - all device logs are published here
* `alerts` - alerts, such as critical errors are logged here
* `status` - each device publishes their state here
* `commands` - devices broadcast commands (such as triggers) here
* `heartbeats` - every device broadcasts a heartbeat, every 5 seconds by default
* `settings` - devices soft-settings are stored here

### Logs

### Alerts

### Status

### Commands

Full Commands documentation: [Commands](Commands.md).

### Heartbeats

### Settings

When a device initialises, it subscribes to its own settings subject at the `LAST` message. It _must_ have a settings
message before it can begin operation, so a new device will wait until a settings object is published.

Publishing a new message to `settings` will force a device to update their settings in real-time.
