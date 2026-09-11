"""Fail-fast startup validation: refuse to boot with an actionable error
rather than starting successfully and failing later inside a request."""

import os

_MANAGER_KEY_LABEL = "AGENT_TRIGGER_API_KEY (or AGENT_API_KEYS)"


def required_vars() -> dict[str, str]:
    return {
        "JWT_SECRET": (
            "verifies customer-presented JWTs on POST /agent/chat "
            "(must match the Java backend's HS512 secret)"
        ),
        "BACKEND_URL": (
            "the MaSoVa platform api-gateway this service calls " "for all customer/ops tools"
        ),
        # Either AGENT_TRIGGER_API_KEY or AGENT_API_KEYS satisfies this.
        # Listed here so required_vars() documents the manager-auth requirement.
        "AGENT_TRIGGER_API_KEY": (
            "required for manager/ops routes (X-Agent-Api-Key auth); "
            "AGENT_API_KEYS JSON is an accepted alternative"
        ),
    }


def _has_manager_key_config() -> bool:
    return bool(os.getenv("AGENT_API_KEYS") or os.getenv("AGENT_TRIGGER_API_KEY"))


def check_environment(strict: bool = True) -> list[str]:
    purposes = required_vars()
    missing = [name for name in ("JWT_SECRET", "BACKEND_URL") if not os.getenv(name)]
    if not _has_manager_key_config():
        missing.append(_MANAGER_KEY_LABEL)

    if strict and missing:
        lines = ["masova-support cannot start — missing required environment variables:"]
        for name in missing:
            purpose = purposes.get(
                name.split(" ")[0],
                "required for manager/ops routes (X-Agent-Api-Key auth)",
            )
            lines.append(f"  - {name}: {purpose}")
        raise EnvironmentError("\n".join(lines))

    return missing
