"""HTTP routes for manager chat, agent registry, and run log."""

import json
import time

import jwt
from fastapi.testclient import TestClient

SECRET = "test-secret-at-least-64-characters-long-for-hs512-aaaaaaaaaaaaaaaaaaaaaa"


def _client(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from masova_agent.main import app

    return TestClient(app, raise_server_exceptions=False)


def test_manager_chat_requires_scope(monkeypatch):
    monkeypatch.setenv("AGENT_API_KEYS", json.dumps([{"key": "k1", "scopes": ["read:runs"]}]))
    client = _client(monkeypatch)
    resp = client.post(
        "/agent/manager/chat", json={"message": "hi"}, headers={"X-Agent-Api-Key": "k1"}
    )
    assert resp.status_code == 403


def test_manager_chat_succeeds_with_scope(monkeypatch):
    monkeypatch.setenv("AGENT_API_KEYS", json.dumps([{"key": "k1", "scopes": ["chat:manager"]}]))
    client = _client(monkeypatch)
    resp = client.post(
        "/agent/manager/chat", json={"message": "hi"}, headers={"X-Agent-Api-Key": "k1"}
    )
    assert resp.status_code == 200
    assert "reply" in resp.json()


def test_customer_jwt_cannot_reach_manager_chat(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.setenv("AGENT_TRIGGER_API_KEY", "legacy-key")
    token = jwt.encode(
        {"sub": "cust-123", "userType": "CUSTOMER", "exp": int(time.time()) + 3600},
        SECRET,
        algorithm="HS512",
    )
    client = _client(monkeypatch)
    resp = client.post(
        "/agent/manager/chat",
        json={"message": "hi"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code in (401, 403)


def test_get_agents_lists_registry(monkeypatch):
    monkeypatch.setenv("AGENT_API_KEYS", json.dumps([{"key": "k1", "scopes": ["read:registry"]}]))
    client = _client(monkeypatch)
    resp = client.get("/agents", headers={"X-Agent-Api-Key": "k1"})
    assert resp.status_code == 200
    names = [a["name"] for a in resp.json()]
    assert "manager_chat" in names
    assert "support_chat" in names


def test_get_agent_runs_requires_scope(monkeypatch):
    monkeypatch.setenv("AGENT_API_KEYS", json.dumps([{"key": "k1", "scopes": ["chat:manager"]}]))
    client = _client(monkeypatch)
    resp = client.get("/agent/runs", headers={"X-Agent-Api-Key": "k1"})
    assert resp.status_code == 403


def test_get_agent_run_by_id_404_when_missing(monkeypatch):
    monkeypatch.setenv("AGENT_API_KEYS", json.dumps([{"key": "k1", "scopes": ["read:runs"]}]))
    client = _client(monkeypatch)
    resp = client.get("/agent/runs/does-not-exist", headers={"X-Agent-Api-Key": "k1"})
    assert resp.status_code == 404
