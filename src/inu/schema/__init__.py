import json
import logging

from ..error import Malformed

logger = logging.getLogger('inu.schema')


class Schema:
    def __init__(self, bootstrap=None, **kwargs):
        if bootstrap is None:
            pass
        elif isinstance(bootstrap, bytearray):
            self.hydrate(bytes(bootstrap))
        elif isinstance(bootstrap, str) or isinstance(bootstrap, bytes):
            self.hydrate(bootstrap)
        elif isinstance(bootstrap, dict):
            self.hydrate_dict(bootstrap)
        else:
            raise Malformed(f"Invalid type for schema bootstrap: {type(bootstrap)}: {bootstrap}")

        if len(kwargs) > 0:
            self.hydrate_dict(kwargs)

    def hydrate(self, payload: str | bytes):
        """
        Hydrate object from a JSON string.
        """
        d = json.loads(payload)

        if not isinstance(d, dict):
            # Super weird bug whereby the first invocation of json.loads returns a str instead of dict.
            # Running the result through the same call again seems to resolve it. Bug was triggered when payload was
            # a bytes object.
            d = json.loads(d)

        self.hydrate_dict(d)

    def hydrate_dict(self, d: dict):
        """
        Hydrate object from a dictionary.
        """
        if not isinstance(d, dict):
            raise Exception(f"d is not a dict: {type(d).__name__}: {d}")

        for k, v in d.items():
            if k[0] == '_':
                logger.warning(f"Attempted to hydrate illegal property '{k}' on {self.__class__.__name__}")
                continue

            if hasattr(self, k):
                if hasattr(self, f"_set_{k}"):
                    fn = getattr(self, f"_set_{k}")
                    fn(v)
                else:
                    setattr(self, k, v)
            else:
                logger.warning(f"No property '{k}' to hydrate on {self.__class__.__name__}")

        if hasattr(self, "_validate"):
            self._validate()

    def marshal(self) -> str:
        """
        Generate JSON from the object properties.
        """
        d = {}
        for k in dir(self):
            if k[0] == '_':
                continue
            v = getattr(self, k)
            if callable(v):
                continue
            d[k] = v
        return json.dumps(d)


class Heartbeat(Schema):
    interval: int = None
    build: int = None
    local_addr: str = None


class Log(Schema):
    level: str = None
    message: str = None

    def _validate(self):
        if self.level is None:
            raise Malformed("Log level cannot be None")

        if self.message is None:
            raise Malformed("Log message cannot be None")

    def __repr__(self):
        return f"<log level={self.level}; message={self.message}>"


class Alert(Schema):
    priority: int = None
    message: str = None

    def _validate(self):
        if self.priority is None:
            raise Malformed("Priority cannot be None")

        if self.message is None:
            raise Malformed("Alert message cannot be None")
