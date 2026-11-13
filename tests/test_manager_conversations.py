"""Durable public manager conversations use credential and exact-store boundaries."""

import base64
import json
import sqlite3

import httpx
import pytest
from fastapi.testclient import TestClient

from masova_agent.main import app
from masova_agent.agents import manager_chat_agent as manager
from masova_agent.runtime import run_store, wrap


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "AGENT_API_KEYS",
        json.dumps(
            [
                {"key": "history-owner-a", "scopes": ["*"]},
                {"key": "history-owner-b", "scopes": ["chat:manager"]},
                {"key": "registry-only", "scopes": ["read:registry"]},
            ]
        ),
    )
    monkeypatch.setenv("MANAGER_CONVERSATION_PATH", str(tmp_path / "conversations.sqlite3"))
    monkeypatch.setattr(run_store, "_RUNS_PATH", str(tmp_path / "runs.jsonl"))
    manager._HISTORY.clear()
    return TestClient(app)


def headers(key="history-owner-a"):
    return {"X-Agent-Api-Key": key}


def chat(client, message, session="thread", store="s1", key="history-owner-a", **extra):
    return client.post(
        "/agent/manager/chat",
        json={"message": message, "sessionId": session, "storeId": store, **extra},
        headers=headers(key),
    )


def history(client, session="thread", store="s1", key="history-owner-a"):
    return client.get(
        f"/agent/manager/conversations/{session}",
        params={"storeId": store or ""},
        headers=headers(key),
    )


def test_completed_chat_is_persisted_and_reopens_public_messages(client):
    response = chat(client, "Check stock for person@example.com")
    assert response.status_code == 200
    assert response.json()["historySaved"] is True
    listing = client.get("/agent/manager/conversations?storeId=s1", headers=headers())
    assert listing.status_code == 200
    assert listing.json()["conversations"][0]["sessionId"] == "thread"
    record = history(client).json()["conversation"]
    assert [row["role"] for row in record["messages"]] == ["user", "assistant"]
    assert record["messages"][0]["text"] == "Check stock for [REDACTED_EMAIL]"
    assert record["messages"][1]["text"] == response.json()["reply"]
    assert set(record["messages"][0]) == {"role", "text", "timestamp"}


def test_history_is_exact_principal_and_store_scoped(client):
    chat(client, "Store one")
    chat(client, "Store two", session="other", store="s2")
    chat(client, "Other principal", key="history-owner-b", session="other")
    assert history(client, store="s2").status_code == 404
    assert history(client, key="history-owner-b").status_code == 404
    for store in [None, ""]:
        listing = client.get(
            "/agent/manager/conversations", params={"storeId": store or ""}, headers=headers()
        )
        assert listing.json()["conversations"] == []
    assert (
        len(
            client.get("/agent/manager/conversations?storeId=s1", headers=headers()).json()[
                "conversations"
            ]
        )
        == 1
    )
    assert history(client).json()["conversation"]["messages"][0]["text"] == "Store one"
    assert client.get("/agent/manager/conversations").status_code == 401
    assert (
        client.get("/agent/manager/conversations", headers=headers("registry-only")).status_code
        == 403
    )


@pytest.mark.asyncio
async def test_restart_reloads_bounded_context_and_excludes_private_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("MANAGER_CONVERSATION_PATH", str(tmp_path / "archive.sqlite3"))
    contexts = []

    async def runtime(*args, **kwargs):
        contexts.append(kwargs["context"]["history"])
        return {
            "reply": "Public answer",
            "private_reasoning": "PRIVATE_THOUGHT",
            "_runtime": {"tool_args": "PRIVATE_ARGUMENTS"},
        }

    monkeypatch.setattr(wrap, "run_ops_agent", runtime)
    for index in range(9):
        manager._HISTORY.clear()  # Simulate fresh process: disk is the context source.
        await manager.run_manager_chat(
            f"Public request {index}", "resume", "s1", principal="RAW_API_KEY"
        )
    assert contexts[1][0]["text"] == "Public request 0"
    assert len(contexts[-1]) == 10
    contents = (tmp_path / "archive.sqlite3").read_bytes()
    assert b"RAW_API_KEY" not in contents
    assert b"PRIVATE_THOUGHT" not in contents
    assert b"PRIVATE_ARGUMENTS" not in contents


def test_history_write_failure_preserves_chat_without_claiming_archive(
    client, monkeypatch, tmp_path
):
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("blocked")
    monkeypatch.setenv("MANAGER_CONVERSATION_PATH", str(blocker / "archive.sqlite3"))
    response = chat(client, "Check inventory")
    assert response.status_code == 200
    assert response.json()["reply"]
    assert response.json()["historySaved"] is False
    assert (
        response.json()["historyError"]
        == "Conversation history unavailable. This response was not saved."
    )
    lookup = history(client)
    assert lookup.status_code == 503
    assert "not-a-directory" not in lookup.text
    assert "history-owner-a" not in lookup.text


def test_voice_archive_contains_public_transcript_reply_only(client, monkeypatch):
    async def transcribe(*args):
        return "Review staffing for person@example.com"

    async def synthesize(*args):
        raise httpx.ConnectError("PRIVATE_PROVIDER_KEY")

    monkeypatch.setattr(manager, "transcribe_manager_audio", transcribe)
    monkeypatch.setattr(manager, "synthesize_manager_reply", synthesize)
    recording = base64.b64encode(b"PRIVATE_RAW_AUDIO").decode()
    response = chat(client, "", audioBase64=recording)
    assert response.status_code == 200
    assert response.json()["audioError"]
    assert response.json()["historySaved"] is True
    record = history(client).json()["conversation"]
    assert record["messages"][0]["text"] == "Review staffing for [REDACTED_EMAIL]"
    encoded = json.dumps(record)
    assert recording not in encoded
    assert "audioBase64" not in encoded
    assert "PRIVATE_PROVIDER_KEY" not in encoded


def test_transcription_failure_does_not_create_fake_archive(client, monkeypatch):
    async def fail(*args):
        raise RuntimeError("PRIVATE_PROVIDER_KEY")

    monkeypatch.setattr(manager, "transcribe_manager_audio", fail)
    assert chat(client, "", audioBase64="YQ==").status_code == 502
    listing = client.get("/agent/manager/conversations?storeId=s1", headers=headers())
    assert listing.json()["conversations"] == []


def test_archive_schema_never_stores_authenticated_credential(client, monkeypatch):
    chat(client, "My API key is history-owner-a")
    import os

    with sqlite3.connect(os.environ["MANAGER_CONVERSATION_PATH"]) as db:
        dump = "\n".join(db.iterdump())
    assert "history-owner-a" not in dump
    assert "principal_hash" in dump
