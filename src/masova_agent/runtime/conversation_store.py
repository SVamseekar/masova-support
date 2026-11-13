"""Bounded public conversation archive. SQLite serializes concurrent completed exchanges.

Storage is opt-in via MANAGER_CONVERSATION_PATH; no default writes into source.
Authentication stays at the HTTP boundary. Every lookup includes the credential hash
and exact store scope, including the separate all-store conversation scope.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .guardrails import screen_output

MAX_CONVERSATIONS = 128
MAX_MESSAGES = 100
CONTEXT_MESSAGES = 10
MAX_TEXT = 2000


class HistoryUnavailable(RuntimeError):
    """Storage is unconfigured, corrupt, inaccessible, or busy beyond the timeout."""


def principal_hash(principal: str) -> str:
    return hashlib.sha256(principal.encode()).hexdigest()


def public_text(text: str, principal: str = "") -> str:
    """Store public text only; never retain configured credentials pasted into a turn."""
    secrets = [
        os.getenv(name, "")
        for name in [
            "AGENT_TRIGGER_API_KEY",
            "GOOGLE_API_KEY",
            "LLM_API_KEY",
            "AGENT_TOKEN",
            "JWT_SECRET",
        ]
    ]
    if principal != "manager":
        secrets.append(principal)
    try:
        keys = json.loads(os.getenv("AGENT_API_KEYS", "[]"))
        secrets.extend(str(row.get("key") or "") for row in keys if isinstance(row, dict))
    except (ValueError, TypeError):
        pass
    result = screen_output(text)
    for secret in sorted(set(secrets), key=len, reverse=True):
        if len(secret) >= 4:
            result = result.replace(secret, "[REDACTED_CREDENTIAL]")
    return result


@contextmanager
def _connection() -> Iterator[sqlite3.Connection]:
    location = os.getenv("MANAGER_CONVERSATION_PATH", "").strip()
    if not location:
        raise HistoryUnavailable("Conversation storage is not configured")
    connection = None
    try:
        path = Path(location).expanduser()
        if not path.is_absolute():
            raise HistoryUnavailable("Conversation storage requires an absolute path")
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(path), timeout=5)
        os.chmod(path, 0o600)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA secure_delete = ON")
        connection.execute("""CREATE TABLE IF NOT EXISTS conversations (
                principal_hash TEXT NOT NULL, store_scope TEXT NOT NULL,
                session_id TEXT NOT NULL, title TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                messages TEXT NOT NULL,
                PRIMARY KEY (principal_hash, store_scope, session_id)
            )""")
        connection.commit()
        yield connection
    except (OSError, sqlite3.Error, ValueError, TypeError) as exc:
        if connection is not None:
            connection.rollback()
        raise HistoryUnavailable("Conversation storage unavailable") from exc
    finally:
        if connection is not None:
            connection.close()


def _scope(principal: str, store_id: str | None, session_id: str) -> tuple[str, str, str]:
    return principal_hash(principal), store_id or "", session_id


def _public_record(row: sqlite3.Row) -> dict:
    stored = json.loads(row["messages"])
    if not isinstance(stored, list):
        raise ValueError("Invalid stored conversation")
    messages = []
    for turn in stored[-MAX_MESSAGES:]:
        if (
            not isinstance(turn, dict)
            or turn.get("role") not in ("user", "assistant")
            or not isinstance(turn.get("text"), str)
            or not isinstance(turn.get("timestamp"), str)
        ):
            raise ValueError("Invalid stored message")
        messages.append(
            {"role": turn["role"], "text": turn["text"][:MAX_TEXT], "timestamp": turn["timestamp"]}
        )
    return {
        "sessionId": row["session_id"],
        "storeId": row["store_scope"] or None,
        "title": row["title"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "messages": messages,
    }


def get_conversation(principal: str, store_id: str | None, session_id: str) -> dict | None:
    with _connection() as db:
        row = db.execute(
            "SELECT * FROM conversations WHERE principal_hash=? AND store_scope=? AND session_id=?",
            _scope(principal, store_id, session_id),
        ).fetchone()
        return _public_record(row) if row is not None else None


def list_conversations(principal: str, store_id: str | None, limit: int = 50) -> list[dict]:
    with _connection() as db:
        rows = db.execute(
            "SELECT * FROM conversations WHERE principal_hash=? AND store_scope=? "
            "ORDER BY updated_at DESC, session_id LIMIT ?",
            (principal_hash(principal), store_id or "", max(1, min(limit, MAX_CONVERSATIONS))),
        ).fetchall()
        result = []
        for row in rows:
            record = _public_record(row)
            record["messageCount"] = len(record.pop("messages"))
            result.append(record)
        return result


def load_context(principal: str, store_id: str | None, session_id: str) -> list[dict[str, str]]:
    record = get_conversation(principal, store_id, session_id)
    if record is None:
        return []
    return [
        {"role": turn["role"], "text": turn["text"]}
        for turn in record["messages"][-CONTEXT_MESSAGES:]
    ]


def append_exchange(
    principal: str, store_id: str | None, session_id: str, user_text: str, assistant_text: str
) -> None:
    """Commit both public messages together; never create half-saved assistant exchanges."""
    scope = _scope(principal, store_id, session_id)
    user_text = public_text(user_text, principal)[:MAX_TEXT]
    assistant_text = public_text(assistant_text, principal)[:MAX_TEXT]
    timestamp = datetime.now(timezone.utc).isoformat()
    with _connection() as db:
        db.execute("BEGIN IMMEDIATE")
        previous = db.execute(
            "SELECT * FROM conversations WHERE principal_hash=? AND store_scope=? AND session_id=?",
            scope,
        ).fetchone()
        messages = _public_record(previous)["messages"] if previous is not None else []
        messages.extend(
            [
                {"role": "user", "text": user_text, "timestamp": timestamp},
                {"role": "assistant", "text": assistant_text, "timestamp": timestamp},
            ]
        )
        db.execute(
            "INSERT OR REPLACE INTO conversations VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                *scope,
                previous["title"] if previous is not None else user_text[:80],
                previous["created_at"] if previous is not None else timestamp,
                timestamp,
                json.dumps(messages[-MAX_MESSAGES:]),
            ),
        )
        # Bound every credential across stores; arbitrary store IDs cannot multiply its archive.
        db.execute(
            "DELETE FROM conversations WHERE principal_hash=? AND rowid NOT IN "
            "(SELECT rowid FROM conversations WHERE principal_hash=? "
            "ORDER BY updated_at DESC, session_id LIMIT ?)",
            (scope[0], scope[0], MAX_CONVERSATIONS),
        )
        db.commit()
