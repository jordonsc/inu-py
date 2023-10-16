from .protocol import ErrorResponse
from .. import error


class JetstreamError(error.MicroNatsError):
    pass


class NotAckable(JetstreamError):
    pass


class ErrorResponseException(JetstreamError):
    def __init__(self, err: ErrorResponse):
        self.err_response = err
        super().__init__()

    def response(self) -> ErrorResponse:
        return self.err_response

    def __repr__(self):
        return self.err_response.description
