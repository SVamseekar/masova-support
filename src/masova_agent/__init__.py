"""
MaSoVa Customer Support Agent

A professional AI agent built with Google ADK for customer support operations.
"""
__version__ = "0.1.0"

from .core import (
    MaSoVaAgent,
    get_agent,
    send_message,
    root_agent,
    agent,
    app,
)
from .utils import get_config, get_logger, setup_logging
from .exceptions import (
    MaSoVaException,
    CustomerNotFoundError,
    OrderNotFoundError,
    LocationServiceError,
    ConfigurationError,
    AgentError,
)

__all__ = [
    # Core
    "MaSoVaAgent",
    "get_agent",
    "send_message",
    "root_agent",
    "agent",
    "app",
    # Utilities
    "get_config",
    "get_logger",
    "setup_logging",
    # Exceptions
    "MaSoVaException",
    "CustomerNotFoundError",
    "OrderNotFoundError",
    "LocationServiceError",
    "ConfigurationError",
    "AgentError",
    # Version
    "__version__",
]
