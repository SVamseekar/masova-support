"""Sliding-window rate limiter, tiered by route sensitivity."""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque

_buckets: dict[tuple[str, str], deque] = defaultdict(deque)

_TIER_BUDGETS = {
    "TIER_AI": int(os.getenv("RATE_LIMIT_AI_PER_MIN", "180")),
    "TIER_READ": int(os.getenv("RATE_LIMIT_READ_PER_MIN", "1200")),
    "TIER_DEFAULT": int(os.getenv("RATE_LIMIT_DEFAULT_PER_MIN", "60")),
}
_WINDOW_SECONDS = 60.0


def _reset_for_tests() -> None:
    _buckets.clear()


def classify_route_tier(path: str, method: str) -> str:
    if path == "/health":
        return "TIER_EXEMPT"
    if path.endswith("/trigger") or path in ("/agent/chat", "/agent/manager/chat"):
        return "TIER_AI"
    if method == "GET":
        return "TIER_READ"
    return "TIER_DEFAULT"


def check_rate_limit(
    key: str,
    tier: str,
    budget: int | None = None,
    window_seconds: float = _WINDOW_SECONDS,
) -> bool:
    if tier == "TIER_EXEMPT":
        return True
    limit = budget if budget is not None else _TIER_BUDGETS.get(tier, _TIER_BUDGETS["TIER_DEFAULT"])
    now = time.monotonic()
    bucket = _buckets[(key, tier)]
    while bucket and now - bucket[0] > window_seconds:
        bucket.popleft()
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True
