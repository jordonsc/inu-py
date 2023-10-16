from micro_nats.model import Model


class Limits(Model):
    def __init__(self, **args):
        self.max_memory: int | None = None
        self.max_storage: int | None = None
        self.max_streams: int | None = None
        self.max_consumers: int | None = None
        self.max_ack_pending: int | None = None
        self.memory_max_stream_bytes: int | None = None
        self.storage_max_stream_bytes: int | None = None
        self.max_bytes_required: bool | None = None
        super().__init__(**args)


class Api(Model):
    def __init__(self, **args):
        self.total: int | None = None
        self.errors: int | None = None
        super().__init__(**args)


class ServerStats(Model):
    def __init__(self, **args):
        self.memory: int | None = None
        self.storage: int | None = None
        self.streams: int | None = None
        self.consumers: int | None = None
        self.limits: Limits = Limits()
        self.api: Api = Api()
        super().__init__(**args)
