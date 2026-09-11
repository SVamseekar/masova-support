"""Scoped API key auth for manager/ops routes. Customer JWT auth in auth.py is untouched."""

from __future__ import annotations

import json
import os

from fastapi import Header, HTTPException


def _load_keys() -> list[dict]:
    raw = os.getenv("AGENT_API_KEYS")
    if raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=503, detail="AGENT_API_KEYS is not valid JSON") from exc
        if isinstance(parsed, list):
            return parsed
        raise HTTPException(status_code=503, detail="AGENT_API_KEYS must be a JSON array")
    legacy = os.getenv("AGENT_TRIGGER_API_KEY")
    if legacy:
        return [{"key": legacy, "scopes": ["*"]}]
    return []


def require_scope(scope: str):
    def _dependency(x_agent_api_key: str | None = Header(default=None)):
        keys = _load_keys()
        if not keys:
            raise HTTPException(status_code=503, detail="Agent API keys not configured")
        if not x_agent_api_key:
            raise HTTPException(status_code=401, detail="Missing X-Agent-Api-Key header")
        match = next((k for k in keys if k.get("key") == x_agent_api_key), None)
        if match is None:
            raise HTTPException(status_code=401, detail="Unknown API key")
        scopes = match.get("scopes") or []
        if "*" in scopes or scope in scopes:
            return match
        raise HTTPException(status_code=403, detail=f"Missing scope: {scope}")

    return _dependency
