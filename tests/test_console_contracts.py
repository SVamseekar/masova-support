"""Console consolidation contracts; providers and backend remain offline."""

import base64
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
import httpx
from fastapi.testclient import TestClient

from masova_agent.main import app
from masova_agent.agents import manager_chat_agent as manager
from masova_agent.runtime import proposal_store, run_store


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "AGENT_API_KEYS",
        json.dumps(
            [
                {"key": "manager-test", "scopes": ["*"]},
                {"key": "chat-only", "scopes": ["chat:manager"]},
            ]
        ),
    )
    monkeypatch.setenv("PROPOSAL_DATA_DIR", str(tmp_path / "proposals"))
    monkeypatch.setattr(run_store, "_RUNS_PATH", str(tmp_path / "runs.jsonl"))
    proposal_store.clear_for_tests()
    return TestClient(app)


HEADERS = {"X-Agent-Api-Key": "manager-test"}


def test_store_transport_failure_returns_redacted_service_unavailable(client, monkeypatch):
    async def unavailable(*args, **kwargs):
        raise httpx.ConnectError("internal-backend-secret")

    monkeypatch.setenv("AGENT_TOKEN", "synthetic-agent-token")
    monkeypatch.setattr(httpx.AsyncClient, "get", unavailable)
    response = client.get("/agent/manager/stores", headers=HEADERS)
    assert response.status_code == 503
    assert (
        response.json()["detail"] == "Store lookup unavailable. Retry when the backend reconnects."
    )
    assert "internal-backend-secret" not in response.text


@pytest.mark.parametrize(
    "payload",
    [
        {"message": "hello", "session_id": "compat", "store_id": "s1"},
        {"message": "hello", "sessionId": "compat", "storeId": "s1"},
    ],
)
def test_manager_both_request_contracts(client, payload):
    response = client.post("/agent/manager/chat", json=payload, headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["session_id"] == response.json()["sessionId"] == "compat"
    assert response.json()["storeId"] == "s1"
    assert response.json()["used_fallback"] is True


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"message": " "},
        {"audioBase64": "not!base64"},
        {"audioBase64": "YQ==", "mimeType": "application/javascript"},
    ],
)
def test_manager_invalid_input_rejected(client, payload):
    assert client.post("/agent/manager/chat", json=payload, headers=HEADERS).status_code == 422


def test_audio_transcript_and_playable_reply(client, monkeypatch):
    async def transcribe(raw, mime_type):
        assert raw == b"recording"
        assert mime_type == "audio/webm"
        return "Check inventory"

    async def synthesize(text):
        return {"audioBase64": "UklGRg==", "mimeType": "audio/wav"}

    monkeypatch.setattr(manager, "transcribe_manager_audio", transcribe, raising=False)
    monkeypatch.setattr(manager, "synthesize_manager_reply", synthesize, raising=False)
    response = client.post(
        "/agent/manager/chat",
        json={
            "sessionId": "voice",
            "audioBase64": base64.b64encode(b"recording").decode(),
            "mimeType": "audio/webm",
        },
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["transcript"] == "Check inventory"
    assert response.json()["mimeType"] == "audio/wav"
    assert "recording" not in str(run_store.list_runs())


def test_transcription_failure_is_explicit_and_redacted(client, monkeypatch):
    async def fail(*args, **kwargs):
        raise RuntimeError("secret-provider-key")

    monkeypatch.setattr(manager, "transcribe_manager_audio", fail, raising=False)
    response = client.post("/agent/manager/chat", json={"audioBase64": "YQ=="}, headers=HEADERS)
    assert response.status_code == 502
    assert "secret-provider-key" not in response.text
    assert run_store.list_runs() == []


def test_tts_failure_keeps_text_and_explicit_audio_error(client, monkeypatch):
    async def transcript(*args, **kwargs):
        return "Check inventory"

    async def fail(*args, **kwargs):
        raise RuntimeError("secret-provider-key")

    monkeypatch.setattr(manager, "transcribe_manager_audio", transcript, raising=False)
    monkeypatch.setattr(manager, "synthesize_manager_reply", fail, raising=False)
    response = client.post("/agent/manager/chat", json={"audioBase64": "YQ=="}, headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["reply"]
    assert response.json()["audioError"] == "Speech unavailable. Text reply preserved."
    assert "secret-provider-key" not in response.text


def test_console_public_shell_and_protected_records(client):
    assert client.get("/console").status_code == 200
    assert client.get("/console-assets/console.js").status_code == 200
    assert client.get("/agent/console").status_code == 401
    response = client.get("/agent/console", headers=HEADERS)
    assert response.status_code == 200
    specialists = response.json()["specialists"]
    assert len(specialists) == 7
    assert {s["scope"] for s in specialists} == {"all_stores", "review_store"}


def test_chat_scope_cannot_resolve_proposals(client):
    response = client.post(
        "/agent/proposals/missing/resolve",
        json={"status": "APPROVED"},
        headers={"X-Agent-Api-Key": "chat-only"},
    )
    assert response.status_code == 403


def save_pending():
    return proposal_store.save_proposal(
        {
            "type": "DRAFT_PURCHASE_ORDER",
            "store_id": "s1",
            "agent": "inventory_reorder",
            "summary": "Review stock",
        }
    )


def test_terminal_decision_conflict_and_idempotent_repeat(client):
    proposal = save_pending()
    url = f"/agent/proposals/{proposal['proposal_id']}/resolve"
    first = client.post(url, json={"status": "APPROVED", "note": "Reviewed"}, headers=HEADERS)
    repeated = client.post(url, json={"status": "APPROVED", "note": "changed"}, headers=HEADERS)
    assert first.json() == repeated.json()
    assert client.post(url, json={"status": "REJECTED"}, headers=HEADERS).status_code == 409
    assert client.post(url, json={"status": "EXPIRED"}, headers=HEADERS).status_code == 400


def test_competing_decisions_only_one_wins(client):
    proposal = save_pending()

    def decide(status):
        try:
            return proposal_store.resolve_proposal(proposal["proposal_id"], status)["status"]
        except ValueError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(decide, ["APPROVED", "REJECTED"]))
    assert results.count("conflict") == 1
    assert len((proposal_store._jsonl_path()).read_text().splitlines()) == 2


def test_run_filters_preserve_legacy_array(client):
    for store, agent in [("s1", "inventory_reorder"), ("s2", "kitchen_coach")]:
        run_store.append_run({"agent": agent, "store_id": store, "status": "ok"})
    response = client.get("/agent/runs?storeId=s1&agent=inventory_reorder", headers=HEADERS)
    assert isinstance(response.json(), list)
    assert len(response.json()) == 1
    assert response.json()[0]["store_id"] == "s1"


def test_validation_response_does_not_echo_audio(client):
    response = client.post(
        "/agent/manager/chat", json={"audioBase64": "private-audio!"}, headers=HEADERS
    )
    assert response.status_code == 422
    assert "private-audio" not in response.text


def test_conflicting_request_aliases_rejected(client):
    response = client.post(
        "/agent/manager/chat",
        json={
            "message": "Check stock",
            "store_id": "s1",
            "storeId": "s2",
        },
        headers=HEADERS,
    )
    assert response.status_code == 422


def test_public_run_records_include_actual_tool_names_and_fallback(client):
    response = client.post("/agent/manager/chat", json={"message": "Check stock"}, headers=HEADERS)
    assert response.status_code == 200
    record = run_store.list_runs()[0]
    assert record["tools_used"] == []
    assert record["used_fallback"] is True
    assert record["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_manager_schema_for_required_tool_input_and_store_binding(monkeypatch):
    captured = {}

    def make_runner(**kwargs):
        captured.update(kwargs)

        async def noop(request):
            return {}

        return noop

    async def read_stock(store_id=""):
        return {"store_id": store_id}

    monkeypatch.setattr(manager, "make_ops_llm_runner", make_runner)
    monkeypatch.setitem(manager.MANAGER_TOOL_FUNCTIONS, "list_low_stock", read_stock)
    manager._manager_llm_runner("s1", ["chat:manager"])
    assert not any(name.startswith("run_") for name in captured["tool_names"])
    assert "list_manager_proposals" not in captured["tool_names"]
    assert "resolve_manager_proposal" not in captured["tool_names"]
    from masova_agent.runtime.ops_llm import invoke_tool

    assert await invoke_tool(captured["tool_functions"]["list_low_stock"], {"store_id": "s2"}) == {
        "store_id": "s1"
    }
    manager._manager_llm_runner(None, ["*"])
    schema = captured["tool_schemas"]["search_ops_manual"]["parameters"]
    assert schema["required"] == ["query"]
    assert schema["properties"]["query"]["type"] == "string"


@pytest.mark.asyncio
async def test_history_isolated_by_principal_and_store(monkeypatch):
    contexts = []
    manager._HISTORY.clear()

    async def runtime(*args, **kwargs):
        contexts.append(kwargs["context"])
        return {"reply": "Read-only response", "_runtime": {"used_fallback": False}}

    from masova_agent.runtime import wrap

    monkeypatch.setattr(wrap, "run_ops_agent", runtime)
    await manager.run_manager_chat("First message", "session", "s1", principal="manager1")
    await manager.run_manager_chat("Second message", "session", "s1", principal="manager1")
    await manager.run_manager_chat("Different key", "session", "s1", principal="manager2")
    await manager.run_manager_chat("Different store", "session", "s2", principal="manager1")
    assert len(contexts[1]["history"]) == 2
    assert contexts[2]["history"] == []
    assert contexts[3]["history"] == []


def test_pcm_speech_is_playable_wav():
    import io
    import wave
    from masova_agent.agents.manager_audio import playable_audio

    output = playable_audio(b"\x01\x00\xff\x7f", "audio/L16;codec=pcm;rate=24000")
    assert output["mimeType"] == "audio/wav"
    with wave.open(io.BytesIO(base64.b64decode(output["audioBase64"]))) as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == 24000
        assert wav.readframes(2) == b"\x01\x00\xff\x7f"


def test_fleet_mixed_text_audio_contract_keeps_text_precedence(client, monkeypatch):
    async def never_transcribe(*args, **kwargs):
        raise AssertionError("Text must take precedence over attached audio")

    async def synthesize(*args, **kwargs):
        return {"audioBase64": "UklGRg==", "mimeType": "audio/wav"}

    monkeypatch.setattr(manager, "transcribe_manager_audio", never_transcribe)
    monkeypatch.setattr(manager, "synthesize_manager_reply", synthesize)
    response = client.post(
        "/agent/manager/chat",
        json={
            "message": "Check inventory",
            "audioBase64": "YQ==",
            "sessionId": "mixed",
        },
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["transcript"] == ""
    assert response.json()["audioBase64"] == "UklGRg=="


@pytest.mark.asyncio
async def test_audio_provider_async_cleanup_on_cancellation(monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock, MagicMock
    from google import genai
    from masova_agent.agents import manager_audio

    started = asyncio.Event()

    async def pending(**kwargs):
        started.set()
        await asyncio.Event().wait()

    client = MagicMock()
    client.aio.models.generate_content = pending
    client.aio.aclose = AsyncMock()
    monkeypatch.setattr(genai, "Client", lambda **kwargs: client)
    task = asyncio.create_task(manager_audio.transcribe_manager_audio(b"audio"))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    client.aio.aclose.assert_awaited_once()
    client.close.assert_called_once()


def test_audio_transcript_uses_existing_output_redaction(client, monkeypatch):
    async def transcript(*args, **kwargs):
        return "Review ops for person@example.com"

    async def speech(*args, **kwargs):
        return {"audioError": "Speech unavailable. Text reply preserved."}

    monkeypatch.setattr(manager, "transcribe_manager_audio", transcript)
    monkeypatch.setattr(manager, "synthesize_manager_reply", speech)
    response = client.post("/agent/manager/chat", json={"audioBase64": "YQ=="}, headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["transcript"] == "Review ops for [REDACTED_EMAIL]"
