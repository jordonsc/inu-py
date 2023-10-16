MicroNats
=========
A light and efficient Python implementation of the _NATS_ SDK compatible with _MicroPython_ and requiring no
non-standard dependencies.

Supported:

* Core NATS
* JetStream
* Authentication (limited testing)

Not Supported:

* Stream snapshot/restore API
* TLS

Non-supported items coming soon.

Architecture
------------
This library avoids the use of Regular Expressions for both efficiency and minimal-dependency reasons. Protocol parsers
therefor use
the [string parsing](https://docs.nats.io/reference/reference-protocols/nats-protocol/nats-client-dev#deciding-on-a-parsing-strategy)
strategy.

Inboxes are created, pooled and recycled for both disposable req/rep queries and consumer subscriptions. This is
handled transparently.

The class structure obeys a strict single-purpose & separation of concerns approach. Data objects are strict models,
and client APIs handle message flow. Thus, unlike _Synadia_ APIs, you would not `ack` from the message object, but
rather by calling the _JetStream_ client's `ack()` function.

Finally, most requests can be made either asynchronously or synchronously. By default, they'll block and return your
response, however you can pass a single-argument callback to the `on_done` parameter and instead it will return
immediately and then pass your result to the callback.

If you use the callback approach, exceptions won't be raised but instead you'll get an `ErrorResponse` object
containing details of the _NATS_ error.

MicroPython Support
-------------------
This library will run on most _MicroPython_ builds (tested on ESP32-S2). You require at least version `1.21` of 
_MicroPython_ for `asyncio` support. 

In addition, you'll require some core libraries that are optional on _MicroPython_, acquired from the
[MicroPython libraries](https://github.com/micropython/micropython-lib):

* `base64`
* `datetime`
* `logging`
