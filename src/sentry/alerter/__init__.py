import logging
from abc import abstractmethod, ABC

import requests

from inu import const


class Alerter(ABC):
    @abstractmethod
    async def publish(self, device_id, message, priority=const.Priority.P2):
        """
        Send a message to the logging engine.
        """
        pass


class PagerDuty(Alerter):
    """
    Performs an HTTP push to a Loki server on every message.
    """

    def __init__(self, cfg):
        self.logger = logging.getLogger('inu.sentry.pagerduty')
        self.routing_key = cfg['key']
        self.target = "https://events.pagerduty.com/v2/enqueue"

    async def publish(self, device_id, message, priority=const.Priority.P2):
        self.logger.debug(f"Alert [{device_id}] P{str(priority)}: {message}")

        sev = "critical" if priority < const.Priority.P3 else "warning"
        payload = {
            "payload": {
                "summary": message,
                "severity": sev,
                "source": device_id
            },
            "routing_key": self.routing_key,
            "event_action": "trigger"
        }

        response = requests.post(self.target, headers={"Content-Type": "application/json"}, json=payload)
        if response.status_code != 202:
            self.logger.error(f"PD error: status: {response.status_code}, response: {response.text}")
