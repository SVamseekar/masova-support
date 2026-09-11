"""SHA-256 hash-chained run store."""

import json

import pytest

from masova_agent.runtime import run_store
from masova_agent.runtime.audit import AuditLogger


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    path = tmp_path / "runs.jsonl"
    monkeypatch.setattr(run_store, "_RUNS_PATH", str(path))
    return path


def test_append_run_adds_hash_fields():
    record = run_store.append_run(
        {"agent": "demand_forecast", "trigger": "manual", "store_id": "s1", "summary": "ok"}
    )
    assert "record_hash" in record
    assert "prev_hash" in record
    assert record["chain_seq"] == 0


def test_chain_links_sequential_records():
    r1 = run_store.append_run({"agent": "a", "trigger": "manual", "store_id": "s1", "summary": "1"})
    r2 = run_store.append_run({"agent": "a", "trigger": "manual", "store_id": "s1", "summary": "2"})
    assert r2["prev_hash"] == r1["record_hash"]
    assert r2["chain_seq"] == 1


def test_verify_chain_true_on_clean_file():
    run_store.append_run({"agent": "a", "trigger": "manual", "store_id": "s1", "summary": "1"})
    run_store.append_run({"agent": "a", "trigger": "manual", "store_id": "s1", "summary": "2"})
    assert run_store.verify_chain() is True


def test_verify_chain_false_on_tampered_file(isolated_store):
    run_store.append_run({"agent": "a", "trigger": "manual", "store_id": "s1", "summary": "1"})
    run_store.append_run({"agent": "a", "trigger": "manual", "store_id": "s1", "summary": "2"})
    lines = isolated_store.read_text().splitlines()
    tampered = json.loads(lines[0])
    tampered["summary"] = "HACKED"
    lines[0] = json.dumps(tampered)
    isolated_store.write_text("\n".join(lines) + "\n")
    assert run_store.verify_chain() is False


def test_list_runs_returns_recent_first():
    run_store.append_run({"agent": "a", "trigger": "manual", "store_id": "s1", "summary": "1"})
    run_store.append_run({"agent": "b", "trigger": "manual", "store_id": "s1", "summary": "2"})
    runs = run_store.list_runs(limit=10)
    assert runs[0]["agent"] == "b"


def test_append_run_receives_already_redacted_summaries():
    """Redaction lives in AuditLogger; run_store hashes what it is given."""
    logger = AuditLogger()
    record = logger._redact({"summary": "ok", "raw_token": "super-secret"})
    stored = run_store.append_run(
        {
            "agent": "support_chat",
            "trigger": "chat",
            "store_id": None,
            "summary": record["summary"],
            "raw_token": record["raw_token"],
        }
    )
    assert stored["raw_token"] == "[REDACTED]"
    assert "super-secret" not in json.dumps(stored)
