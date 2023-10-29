NATS Streams
============
The veins that control the Inu framework are NATS JetStream streams. All communication is via streams.

Core Streams
------------

 * `logs` - all device logs are published here
 * `alerts` - alerts, such as critical errors are logged here
 * `status` - each device publishes their state here
 * `commands` - devices broadcast commands (such as triggers) here
 * `heartbeats` - every device broadcasts a heartbeat, every 5 seconds by default
 * `settings` - devices soft-settings are stored here

Publishing a new message to `settings` will force a device to update their settings in real-time.
