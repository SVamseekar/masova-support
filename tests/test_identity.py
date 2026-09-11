"""Scoped AGENT_API_KEYS for manager/ops routes."""

import json

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from masova_agent.runtime.identity import require_scope


def make_app(monkeypatch, keys):
    monkeypatch.setenv("AGENT_API_KEYS", json.dumps(keys))
    app = FastAPI()

    @app.get("/protected")
    def protected(_=Depends(require_scope("read:proposals"))):
        return {"ok": True}

    return TestClient(app)


def test_valid_scope_passes(monkeypatch):
    client = make_app(monkeypatch, [{"key": "k1", "scopes": ["read:proposals"]}])
    resp = client.get("/protected", headers={"X-Agent-Api-Key": "k1"})
    assert resp.status_code == 200


def test_missing_scope_403(monkeypatch):
    client = make_app(monkeypatch, [{"key": "k1", "scopes": ["read:runs"]}])
    resp = client.get("/protected", headers={"X-Agent-Api-Key": "k1"})
    assert resp.status_code == 403


def test_unknown_key_401(monkeypatch):
    client = make_app(monkeypatch, [{"key": "k1", "scopes": ["read:proposals"]}])
    resp = client.get("/protected", headers={"X-Agent-Api-Key": "wrong"})
    assert resp.status_code == 401


def test_missing_header_401(monkeypatch):
    client = make_app(monkeypatch, [{"key": "k1", "scopes": ["read:proposals"]}])
    resp = client.get("/protected")
    assert resp.status_code == 401


def test_wildcard_scope_passes(monkeypatch):
    client = make_app(monkeypatch, [{"key": "k1", "scopes": ["*"]}])
    resp = client.get("/protected", headers={"X-Agent-Api-Key": "k1"})
    assert resp.status_code == 200


def test_fallback_to_agent_trigger_api_key_when_unset(monkeypatch):
    monkeypatch.delenv("AGENT_API_KEYS", raising=False)
    monkeypatch.setenv("AGENT_TRIGGER_API_KEY", "legacy-key")
    app = FastAPI()

    @app.get("/protected")
    def protected(_=Depends(require_scope("trigger:demand_forecast"))):
        return {"ok": True}

    client = TestClient(app)
    resp = client.get("/protected", headers={"X-Agent-Api-Key": "legacy-key"})
    assert resp.status_code == 200


def test_unconfigured_keys_return_503(monkeypatch):
    monkeypatch.delenv("AGENT_API_KEYS", raising=False)
    monkeypatch.delenv("AGENT_TRIGGER_API_KEY", raising=False)
    app = FastAPI()

    @app.get("/protected")
    def protected(_=Depends(require_scope("read:proposals"))):
        return {"ok": True}

    client = TestClient(app)
    resp = client.get("/protected", headers={"X-Agent-Api-Key": "k1"})
    assert resp.status_code == 503
