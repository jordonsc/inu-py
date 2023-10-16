from ...model import Model

"""
Consumer models.

See: https://docs.nats.io/nats-concepts/jetstream/consumers
"""


class ConsumerConfig(Model):
    class AckPolicy:
        NONE = "none"
        ALL = "all"
        EXPLICIT = "explicit"

    class DeliverPolicy:
        ALL = "all"
        LAST = "last"
        NEW = "new"
        LAST_PER_SUBJECT = "last_per_subject"
        BY_START_SEQUENCE = "by_start_sequence"
        BY_START_TIME = "by_start_time"

    class ReplayPolicy:
        INSTANT = "instant"
        ORIGINAL = "original"

    def __init__(self, **args):
        """
        NB. that all consumers should have a name, durable and ephemeral alike.

        The field `durable_name` was deprecated in v2.9, however is still required for durable consumers. The API will
        manage this, instead always just set the `name` field.
        """
        self.name: str | None = None
        self.durable_name: str | None = None  # Don't set directly, just use `name`.
        self.description: str | None = None
        self.deliver_subject: str | None = None
        self.deliver_group: str | None = None
        self.deliver_policy: str | None = self.DeliverPolicy.ALL
        self.opt_start_seq: int | None = None
        self.opt_start_time: str | None = None  # in format "2023-01-01T00:00:00Z"
        self.ack_policy: str | None = self.AckPolicy.EXPLICIT
        self.ack_wait: float | None = None  # nanoseconds
        self.max_deliver: int | None = None
        self.filter_subject: str | None = None
        self.replay_policy: str | None = self.ReplayPolicy.INSTANT
        self.sample_freq: str | None = None
        self.rate_limit_bps: int | None = None
        self.max_waiting: int | None = None
        self.max_ack_pending: int | None = None
        self.flow_control: bool | None = None
        self.idle_heartbeat: float | None = None
        self.headers_only: bool | None = None
        self.num_replicas: int | None = None

        super().__init__(**args)


class ConsumerInfo(Model):
    def __init__(self, **args):
        self.stream_name: str | None = None
        self.name: str | None = None
        self.created: str | None = None
        self.num_ack_pending: int | None = None
        self.num_redelivered: int | None = None
        self.num_waiting: int | None = None
        self.num_pending: int | None = None
        self.push_bound: bool | None = None
        self.config: ConsumerConfig = ConsumerConfig()

        super().__init__(**args)

    def __repr__(self):
        return f"<consumer name={self.name}; stream={self.stream_name}>"

    def is_push(self):
        return self.push_bound == True


class ConsumerCreateResponse(ConsumerInfo):
    def __init__(self, **args):
        super().__init__(**args)


class ConsumerDeleteResponse(Model):
    def __init__(self, **args):
        self.success: bool | None = None

        super().__init__(**args)


class Consumer:
    def __init__(self, stream_name: str, consumer_cfg: ConsumerConfig, is_durable: bool = False):
        self.stream_name: str = stream_name
        self.consumer_cfg: ConsumerConfig = consumer_cfg
        self.is_durable: bool = is_durable
