"""The answers the API gives when it cannot serve a request: a closed set of codes, one status and one message each.

Guards, services and routers raise ApiFailure; the application turns it into the same JSON body for every case.
"""

from api.schemas import ApiErrorCode

STATUS = {
    ApiErrorCode.UNAUTHORIZED: 401,
    ApiErrorCode.NOT_FOUND: 404,
    ApiErrorCode.CONFIRMATION_EXPIRED: 409,
    ApiErrorCode.RATE_LIMITED: 429,
    ApiErrorCode.PROVIDER_UNAVAILABLE: 503,
}
MESSAGES = {
    ApiErrorCode.UNAUTHORIZED: "Session missing, invalid or expired",
    ApiErrorCode.NOT_FOUND: "Not found",
    ApiErrorCode.RATE_LIMITED: "Too many messages; wait a minute",
    ApiErrorCode.PROVIDER_UNAVAILABLE: "Service temporarily unavailable; try again in a moment",
}


class ApiFailure(Exception):
    def __init__(self, code: ApiErrorCode) -> None:
        super().__init__(code.value)
        self.code = code

    @property
    def status(self) -> int:
        return STATUS[self.code]

    @property
    def message(self) -> str:
        return MESSAGES.get(self.code, self.code.value.replace("_", " "))
