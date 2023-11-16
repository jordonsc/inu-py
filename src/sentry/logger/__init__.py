import logging
from abc import abstractmethod, ABC

import requests


class Logger(ABC):
    @abstractmethod
    async def publish(self, stream: str, ts: int, msg: str, labels: dict):
        """
        Send a message to the logging engine.

        `stream` should be the NATS stream we're logging
        `ts` should be the message timestamp in nanoseconds
        `msg` should be a text log line
        `labels` should be a dict of relevant labels, such a device_id, priority, etc
        """
        pass


class LokiLogger(Logger):
    """
    Performs an HTTP push to a Loki server on every message.
    """

    def __init__(self, cfg):
        self.logger = logging.getLogger('inu.sentry.loki')
        self.target = cfg['target']

    async def publish(self, stream: str, ts: int, msg: str, labels: dict):
        self.logger.debug(f"Publish [{stream}] {msg}")

        labels["stream"] = stream
        payload = {
            "streams": [
                {
                    "stream": labels,
                    "values": [[str(ts), str(msg)]]
                }
            ]
        }

        response = requests.post(self.target, headers={"Content-Type": "application/json"}, json=payload)
        if response.status_code != 204:
            self.logger.error(f"Loki error: status: {response.status_code}, response: {response.text}")
