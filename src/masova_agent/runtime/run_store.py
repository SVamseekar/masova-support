"""Tamper-evident hash-chained run log (JSONL, sha256(prev_hash + canonical_json(record)))."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone

_RUNS_PATH = os.getenv("RUN_STORE_PATH", "data/runs/runs.jsonl")


def _canonical(record: dict) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"))


def _read_all() -> list[dict]:
    if not os.path.exists(_RUNS_PATH):
        return []
    with open(_RUNS_PATH, "r") as f:
        return [json.loads(line) for line in f if line.strip()]


def append_run(record: dict) -> dict:
    parent = os.path.dirname(_RUNS_PATH)
    if parent:
        os.makedirs(parent, exist_ok=True)
    existing = _read_all()
    prev_hash = existing[-1]["record_hash"] if existing else "0" * 64
    record = dict(record)
    record.setdefault("run_id", str(uuid.uuid4()))
    record.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    record["chain_seq"] = len(existing)
    record["prev_hash"] = prev_hash
    record["record_hash"] = hashlib.sha256((prev_hash + _canonical(record)).encode()).hexdigest()
    with open(_RUNS_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")
    return record


def verify_chain(path: str | None = None) -> bool:
    target = path or _RUNS_PATH
    if not os.path.exists(target):
        return True
    with open(target, "r") as f:
        lines = [json.loads(line) for line in f if line.strip()]
    prev_hash = "0" * 64
    for record in lines:
        stored_hash = record["record_hash"]
        recomputed_input = dict(record)
        recomputed_input.pop("record_hash")
        expected = hashlib.sha256((prev_hash + _canonical(recomputed_input)).encode()).hexdigest()
        if expected != stored_hash or record["prev_hash"] != prev_hash:
            return False
        prev_hash = stored_hash
    return True


def list_runs(limit: int = 100) -> list[dict]:
    return list(reversed(_read_all()))[:limit]


def get_run(run_id: str) -> dict | None:
    for record in _read_all():
        if record.get("run_id") == run_id:
            return record
    return None
