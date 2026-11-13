"""SQLite archive bounds, process reload, and atomicity using real storage."""

import json
import os
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

from masova_agent.runtime import conversation_store as store


@pytest.fixture(autouse=True)
def storage(monkeypatch, tmp_path):
    monkeypatch.setenv("MANAGER_CONVERSATION_PATH", str(tmp_path / "archive.sqlite3"))


def test_archive_messages_and_model_context_have_independent_bounds():
    for index in range(65):
        store.append_exchange("principal", "s1", "conversation", f"Request {index}", "A" * 3000)
    record = store.get_conversation("principal", "s1", "conversation")
    assert len(record["messages"]) == 100
    assert record["messages"][0]["text"] == "Request 15"
    assert len(record["messages"][1]["text"]) == 2000
    assert len(store.load_context("principal", "s1", "conversation")) == 10
    assert record["title"] == "Request 0"
    assert store.list_conversations("principal", "s1")[0]["messageCount"] == 100


def test_conversations_bound_applies_to_principal_across_arbitrary_stores():
    for index in range(131):
        store.append_exchange("principal", f"store-{index}", str(index), "Request", "Answer")
    assert store.get_conversation("principal", "store-0", "0") is None
    assert store.get_conversation("principal", "store-130", "130") is not None
    store.append_exchange("other", "store-0", "0", "Separate", "Answer")
    assert store.get_conversation("other", "store-0", "0") is not None
    with sqlite3.connect(os.environ["MANAGER_CONVERSATION_PATH"]) as db:
        assert db.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] == 129


def test_concurrent_writers_preserve_complete_exchanges():
    def append(index):
        store.append_exchange("principal", "s1", "thread", f"Request {index}", f"Answer {index}")

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(append, range(20)))
    messages = store.get_conversation("principal", "s1", "thread")["messages"]
    assert len(messages) == 40
    assert {message["text"] for message in messages[::2]} == {f"Request {i}" for i in range(20)}
    for user, assistant in zip(messages[::2], messages[1::2]):
        assert user["role"] == "user"
        assert assistant["role"] == "assistant"
        assert user["text"].split()[-1] == assistant["text"].split()[-1]


def test_commit_failure_rolls_back_exchange_and_preserves_existing_thread():
    store.append_exchange("principal", "s1", "thread", "Original", "Answer")
    with sqlite3.connect(os.environ["MANAGER_CONVERSATION_PATH"]) as db:
        db.execute(
            "CREATE TRIGGER fail_write BEFORE INSERT ON conversations "
            "BEGIN SELECT RAISE(ABORT, 'PRIVATE_ERROR'); END"
        )
    with pytest.raises(store.HistoryUnavailable):
        store.append_exchange("principal", "s1", "thread", "Unsaved", "Answer")
    record = store.get_conversation("principal", "s1", "thread")
    assert len(record["messages"]) == 2
    assert record["messages"][0]["text"] == "Original"


def test_fresh_python_process_restores_durable_context():
    store.append_exchange("principal", "s1", "thread", "Persisted", "Answer")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json; from masova_agent.runtime.conversation_store import load_context; "
            "print(json.dumps(load_context('principal', 's1', 'thread')))",
        ],
        env=dict(os.environ),
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout)[0]["text"] == "Persisted"


def test_unconfigured_or_corrupt_storage_is_explicit(monkeypatch):
    path = os.environ["MANAGER_CONVERSATION_PATH"]
    monkeypatch.delenv("MANAGER_CONVERSATION_PATH")
    with pytest.raises(store.HistoryUnavailable):
        store.list_conversations("principal", "s1")
    monkeypatch.setenv("MANAGER_CONVERSATION_PATH", path)
    with open(path, "wb") as db:
        db.write(b"not sqlite")
    with pytest.raises(store.HistoryUnavailable):
        store.get_conversation("principal", "s1", "thread")


def test_storage_read_rejects_malformed_messages_and_never_exposes_extra_fields():
    store.append_exchange("principal", "s1", "thread", "Request", "Answer")
    with sqlite3.connect(os.environ["MANAGER_CONVERSATION_PATH"]) as db:
        db.execute(
            "UPDATE conversations SET messages=?",
            (
                json.dumps(
                    [
                        {
                            "role": "user",
                            "text": "Public",
                            "timestamp": "now",
                            "private_reasoning": "PRIVATE",
                        }
                    ]
                ),
            ),
        )
    record = store.get_conversation("principal", "s1", "thread")
    assert set(record["messages"][0]) == {"role", "text", "timestamp"}
    with sqlite3.connect(os.environ["MANAGER_CONVERSATION_PATH"]) as db:
        db.execute("UPDATE conversations SET messages=?", (json.dumps({"invalid": "shape"}),))
    with pytest.raises(store.HistoryUnavailable):
        store.get_conversation("principal", "s1", "thread")
