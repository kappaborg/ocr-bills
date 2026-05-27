from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class _Bucket:
    tokens: float
    last_ts: float


class InMemoryTokenBucket:
    """
    Minimal in-memory rate limiter.

    Good enough for single-process dev/MVP. For multi-worker production, replace with Redis.
    """

    def __init__(self) -> None:
        self._buckets: dict[str, _Bucket] = {}

    def reset(self) -> None:
        """Clear all buckets — used by the test suite between tests."""
        self._buckets.clear()

    def allow(self, key: str, *, capacity: float, refill_per_sec: float) -> bool:
        now = time.time()
        b = self._buckets.get(key)
        if b is None:
            self._buckets[key] = _Bucket(tokens=capacity - 1.0, last_ts=now)
            return True

        elapsed = max(0.0, now - b.last_ts)
        b.last_ts = now
        b.tokens = min(capacity, b.tokens + elapsed * refill_per_sec)
        if b.tokens >= 1.0:
            b.tokens -= 1.0
            return True
        return False


live_ocr_limiter = InMemoryTokenBucket()

