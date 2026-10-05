"""A sliding window of one minute per key: messages per customer and logins per address."""

from collections import defaultdict, deque
from collections.abc import Callable
from datetime import datetime, timedelta

from api.failures import ApiFailure
from api.schemas import ApiErrorCode

WINDOW = timedelta(minutes=1)


class RateLimiter:
    def __init__(self, per_minute: int, now: Callable[[], datetime]) -> None:
        self._per_minute = per_minute
        self._now = now
        self._calls: defaultdict[str, deque[datetime]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = self._now()
        calls = self._calls[key]
        while calls and now - calls[0] > WINDOW:
            calls.popleft()
        if len(calls) >= self._per_minute:
            raise ApiFailure(ApiErrorCode.RATE_LIMITED)
        calls.append(now)
