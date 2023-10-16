import random

from inu import Inu
from inu.const import Context

DEVICE_ID = ["unittest", f"i{random.randint(1000, 9999)}"]
TEST_SERVER = 'nats://localhost:4222'


def create_context(**params):
    return Context(
        device_id=DEVICE_ID,
        nats_server=TEST_SERVER,
        **params
    )


def create_inu(**params):
    return Inu(create_context(**params))
