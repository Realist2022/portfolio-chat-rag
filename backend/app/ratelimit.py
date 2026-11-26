"""A per-IP sliding-window rate limit, held in memory.

Per Cloud Run instance, so a determined caller spread across instances gets more.
That's fine: it stops the cheap abuse, and the portfolio's route limits first.
"""

import time
from collections import defaultdict, deque

from fastapi import Request


def client_ip(request: Request) -> str:
    # Cloud Run puts the caller's address first in X-Forwarded-For.
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimiter:
    def __init__(self, limit: int, window_seconds: int, clock=time.monotonic):
        self.limit = limit
        self.window = window_seconds
        self.clock = clock
        self._seen: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = self.clock()
        times = self._seen[key]
        while times and now - times[0] > self.window:
            times.popleft()
        if len(times) >= self.limit:
            return False
        times.append(now)
        return True
