from ...model import Model

"""
Stream models.

See: https://docs.nats.io/nats-concepts/jetstream/streams
"""


class Placement(Model):
    def __init__(self, **args):
        self.cluster: str | None = None
        self.tags: list[str] | None = None

        super().__init__(**args)


class StreamSource(Model):
    def __init__(self, **args):
        self.name: str | None = None
        self.opt_start_seq: int | None = None
        self.opt_start_time: str | None = None
        self.filter_subject: str | None = None
        self.external: str | None = None

        super().__init__(**args)


class StreamConfig(Model):
    class RetentionPolicy:
        LIMITS = "limits"
        INTEREST = "interest"
        WORK_QUEUE = "workqueue"

    class StorageType(Model):
        FILE = "file"
        MEMORY = "memory"

    class DiscardPolicy(Model):
        OLD = "old"
        NEW = "new"

    def __init__(self, **args):
        self.name: str | None = None
        self.description: str | None = None
        self.subjects: list[str] | None = None
        self.retention: str | None = self.RetentionPolicy.LIMITS
        self.max_consumers: int | None = None
        self.max_msgs: int | None = None
        self.max_bytes: int | None = None
        self.discard: str | None = self.DiscardPolicy.OLD
        self.max_age: float | None = None
        self.max_msgs_per_subject: int = -1
        self.max_msg_size: int | None = -1
        self.storage: str | None = self.StorageType.FILE
        self.num_replicas: int | None = None
        self.no_ack: bool = False
        self.template_owner: str | None = None
        self.duplicate_window: int = 0
        self.placement: Placement | None = None
        self.mirror: StreamSource | None = None
        self.sources: list[StreamSource] | None = None
        self.sealed: bool = False
        self.deny_delete: bool = False
        self.deny_purge: bool = False
        self.allow_rollup_hdrs: bool = False

        super().__init__(**args)


class PeerInfo(Model):
    def __init__(self, **args):
        self.name: str | None = None
        self.current: bool | None = None
        self.offline: bool | None = None
        self.active: int | None = None
        self.lag: int | None = None

        super().__init__(**args)


class ClusterInfo(Model):
    def __init__(self, **args):
        self.leader: str | None = None
        self.name: str | None = None
        self.replicas: list[PeerInfo] | None = None

        super().__init__(**args)


class StreamState(Model):
    def __init__(self, **args):
        self.messages: int | None = None
        self.bytes: int | None = None
        self.first_seq: int | None = None
        self.last_seq: int | None = None
        self.consumer_count: int | None = None
        self.deleted: list[int] | None = None
        self.num_deleted: int | None = None

        super().__init__(**args)


class StreamInfo(Model):
    def __init__(self, **args):
        self.config: StreamConfig = StreamConfig()
        self.created: str | None = None
        self.state: StreamState = StreamState()
        self.cluster: ClusterInfo = ClusterInfo()

        super().__init__(**args)

    def __repr__(self):
        return f"<stream name={self.config.name}; desc={self.config.description}>"


class StreamMessage(Model):
    def __init__(self, **args):
        self.subject: str | None = None
        self.seq: int | None = None
        self.data: str | None = None
        self.time: str | None = None

        super().__init__(**args)


class StreamMessageResponse(Model):
    def __init__(self, **args):
        self.message: StreamMessage = StreamMessage()

        super().__init__(**args)


class StreamCreateResponse(Model):
    def __init__(self, **args):
        self.config: StreamConfig = StreamConfig()
        self.did_create: bool | None = None

        super().__init__(**args)


class StreamUpdateResponse(Model):
    def __init__(self, **args):
        self.config: StreamConfig = StreamConfig()

        super().__init__(**args)


class StreamDeleteResponse(Model):
    def __init__(self, **args):
        self.success: bool | None = None

        super().__init__(**args)


class StreamPurgeResponse(Model):
    def __init__(self, **args):
        self.success: bool | None = None
        self.purged: int | None = None

        super().__init__(**args)


class MessageDeleteResponse(Model):
    def __init__(self, **args):
        self.success: bool | None = None

        super().__init__(**args)
