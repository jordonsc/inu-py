import asyncio
import json

from . import consumer, stream, server
from ... import error
from ...model import Message, Model

RESPONSE_MAP = {
    'io.nats.jetstream.api.v1.account_info_response': server.ServerStats,

    'io.nats.jetstream.api.v1.stream_info_response': stream.StreamInfo,
    'io.nats.jetstream.api.v1.stream_msg_get_response': stream.StreamMessageResponse,
    'io.nats.jetstream.api.v1.stream_create_response': stream.StreamCreateResponse,
    'io.nats.jetstream.api.v1.stream_update_response': stream.StreamUpdateResponse,
    'io.nats.jetstream.api.v1.stream_delete_response': stream.StreamDeleteResponse,
    'io.nats.jetstream.api.v1.stream_purge_response': stream.StreamPurgeResponse,
    'io.nats.jetstream.api.v1.stream_msg_delete_response': stream.MessageDeleteResponse,

    'io.nats.jetstream.api.v1.consumer_create_response': consumer.ConsumerCreateResponse,
    'io.nats.jetstream.api.v1.consumer_info_response': consumer.ConsumerInfo,
    'io.nats.jetstream.api.v1.consumer_delete_response': consumer.ConsumerDeleteResponse,
}


class ErrorResponse(Model):
    """
    A response from the NATS server containing an error.

    If `code` is set to 0, the object may contain a local error with special `err_codes`:
       0  Generic error
      -1  Not connected
      -2  Timeout
      -3  Cancelled
      -4  Malformed response payload
     -10  JSON parse error
     -11  No 'type' in payload
     -12  Unknown response schema
    """

    def __init__(self, **args):
        self.code: int | None = None
        self.err_code: int | None = None
        self.description: str | None = None
        super().__init__(**args)

    def __repr__(self):
        return f"<error {self.code}/{self.err_code}; {self.description}>"


def from_msg(msg: Message):
    """
    Return a Model object matching the payload in `msg`.

    Returns an ErrorResponse with code and err_code of 0 if there were parsing issues.
    """
    try:
        data = msg.from_json()
    except json.JSONDecodeError:
        return ErrorResponse(code=0, err_code=-10, description="Unable to parse message as JSON")

    if 'error' in data:
        return ErrorResponse(**data['error'])

    if 'type' not in data:
        return ErrorResponse(code=0, err_code=-11, description=f"Payload missing 'type' identifier: {data}")

    if data['type'] not in RESPONSE_MAP:
        return ErrorResponse(code=0, err_code=-12, description=f"Unknown response schema: {data['type']}")

    return RESPONSE_MAP[data['type']](**data)


def from_exception(e: Exception) -> Model:
    """
    Creates an ErrorResponse from an exception.
    """
    if isinstance(e, error.NoConnectionError) or isinstance(e, error.ConnectionRefused):
        return ErrorResponse(code=0, err_code=-1, description="Not connected to server")
    elif isinstance(e, error.NetworkTimeout):
        return ErrorResponse(code=0, err_code=-2, description="Timeout error")
    elif isinstance(e, asyncio.CancelledError):
        return ErrorResponse(code=0, err_code=-3, description="Cancelled")
    elif isinstance(e, error.ParseError) or isinstance(e, error.Malformed):
        return ErrorResponse(code=0, err_code=-4, description="Malformed response payload")
    else:
        return ErrorResponse(code=0, err_code=0, description=f"<{type(e).__name__}> {str(e)}")


class API:
    PREFIX = "$JS.API"

    INFO = "{prefix}.INFO"

    STREAM_LIST = "{prefix}.STREAM.LIST"
    STREAM_NAMES = "{prefix}.STREAM.NAMES"
    STREAM_CREATE = "{prefix}.STREAM.CREATE.{stream}"
    STREAM_UPDATE = "{prefix}.STREAM.UPDATE.{stream}"
    STREAM_INFO = "{prefix}.STREAM.INFO.{stream}"
    STREAM_DELETE = "{prefix}.STREAM.DELETE.{stream}"
    STREAM_PURGE = "{prefix}.STREAM.PURGE.{stream}"
    STREAM_MSG_DEL = "{prefix}.STREAM.MSG.DELETE.{stream}"
    STREAM_MSG_GET = "{prefix}.STREAM.MSG.GET.{stream}"
    STREAM_SNAPSHOT = "{prefix}.STREAM.SNAPSHOT.{stream}"
    STREAM_RESTORE = "{prefix}.STREAM.RESTORE.{stream}"

    CONSUMER_LIST = "{prefix}.CONSUMER.LIST.{stream}"
    CONSUMER_NAMES = "{prefix}.CONSUMER.NAMES.{stream}"
    CONSUMER_CREATE_EPHEMERAL = "{prefix}.CONSUMER.CREATE.{stream}"
    CONSUMER_CREATE_DURABLE = "{prefix}.CONSUMER.DURABLE.CREATE.{stream}.{consumer}"
    CONSUMER_INFO = "{prefix}.CONSUMER.INFO.{stream}.{consumer}"
    CONSUMER_DELETE = "{prefix}.CONSUMER.DELETE.{stream}.{consumer}"
    CONSUMER_MSG_NEXT = "{prefix}.CONSUMER.MSG.NEXT.{stream}.{consumer}"

    @staticmethod
    def get(api: str, prefix: str = None, **args) -> str:
        if prefix is None:
            prefix = API.PREFIX

        return api.format(api, prefix=prefix, **args)
