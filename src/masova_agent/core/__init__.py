"""Core agent module.

Lazy re-exports avoid a circular import:
`agent.py` → `core.redis_session_service` → `core.__init__` → `core.agent` → `agent.py`.
"""

from typing import Any

__all__ = [
    "MaSoVaAgent",
    "get_agent",
    "send_message",
    "root_agent",
    "agent",
    "app",
]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from .agent import MaSoVaAgent, get_agent, send_message, root_agent, agent, app

        mapping = {
            "MaSoVaAgent": MaSoVaAgent,
            "get_agent": get_agent,
            "send_message": send_message,
            "root_agent": root_agent,
            "agent": agent,
            "app": app,
        }
        return mapping[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
