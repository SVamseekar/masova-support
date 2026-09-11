"""Circuit breaker for LLM calls: opens after consecutive failures, half-open trial after cooldown."""

from __future__ import annotations

import time
from enum import Enum

_OPEN_AFTER = 3
_COOLDOWN_SECONDS = 30.0

_failures: dict[str, int] = {}
_opened_at: dict[str, float] = {}
_half_open_pending: dict[str, bool] = {}


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


def _reset_for_tests() -> None:
    _failures.clear()
    _opened_at.clear()
    _half_open_pending.clear()


def record_failure(agent: str) -> None:
    _failures[agent] = _failures.get(agent, 0) + 1
    if _failures[agent] >= _OPEN_AFTER and agent not in _opened_at:
        _opened_at[agent] = time.monotonic()
    elif agent in _half_open_pending:
        _half_open_pending[agent] = False
        _opened_at[agent] = time.monotonic()


def record_success(agent: str) -> None:
    _failures[agent] = 0
    _opened_at.pop(agent, None)
    _half_open_pending.pop(agent, None)


def allow_llm(agent: str) -> bool:
    if agent not in _opened_at:
        return True
    elapsed = time.monotonic() - _opened_at[agent]
    if elapsed < _COOLDOWN_SECONDS:
        return False
    if not _half_open_pending.get(agent, False):
        _half_open_pending[agent] = True
        return True
    return False
