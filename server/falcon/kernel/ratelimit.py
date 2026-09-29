"""Sliding-window rate limiter (single process; FALCON runs one API process)."""
from __future__ import annotations

import threading
import time
from collections import deque


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str) -> float | None:
        """Record a hit. Returns None when allowed, else seconds until retry."""
        now = time.monotonic()
        with self._lock:
            bucket = self._hits.setdefault(key, deque())
            while bucket and bucket[0] <= now - self.window:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return max(0.0, bucket[0] + self.window - now)
            bucket.append(now)
            if len(self._hits) > 10_000:  # bound memory under a spray of keys
                for stale in [k for k, v in self._hits.items() if not v][:5_000]:
                    del self._hits[stale]
            return None

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
