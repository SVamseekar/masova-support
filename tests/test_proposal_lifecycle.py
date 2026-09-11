"""Proposal SUPERSEDED status and 72h expiry sweep."""

from datetime import datetime, timedelta, timezone

import pytest

from masova_agent.runtime import proposal_expiry, proposal_store
from masova_agent.runtime.models import ProposalStatus


@pytest.fixture(autouse=True)
def _isolate_store(monkeypatch, tmp_path):
    monkeypatch.setenv("PROPOSAL_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(proposal_store, "_load_file_once", lambda: None)
    proposal_store._by_id.clear()
    yield
    proposal_store._by_id.clear()


def setup_function():
    proposal_store._by_id.clear()


def _save(**kwargs):
    payload = {
        "type": kwargs.get("proposal_type", "DRAFT_PURCHASE_ORDER"),
        "agent": kwargs.get("agent", "inventory_reorder"),
        "store_id": kwargs.get("store_id", "s1"),
        "summary": "draft",
        "rationale": "test",
        "payload": {},
    }
    return proposal_store.save_proposal(payload)


def test_superseded_is_a_valid_status():
    assert ProposalStatus.SUPERSEDED == "SUPERSEDED"


def test_newer_proposal_supersedes_older_pending_same_type_and_store():
    p1 = _save()
    p2 = _save()
    reloaded_p1 = proposal_store.get_proposal(p1["proposal_id"])
    assert reloaded_p1["status"] == ProposalStatus.SUPERSEDED.value
    assert proposal_store.get_proposal(p2["proposal_id"])["status"] == ProposalStatus.PENDING.value


def test_approved_proposal_not_superseded_by_newer_duplicate():
    p1 = _save()
    proposal_store.resolve_proposal(p1["proposal_id"], ProposalStatus.APPROVED.value, "ok")
    _save()
    assert proposal_store.get_proposal(p1["proposal_id"])["status"] == ProposalStatus.APPROVED.value


def test_sweep_expires_stale_pending():
    p1 = _save(agent="churn_prevention", store_id="s2", proposal_type="DRAFT_CHURN_CAMPAIGN")
    stale_time = (datetime.now(timezone.utc) - timedelta(hours=73)).isoformat()
    proposal_store._by_id[p1["proposal_id"]]["created_at"] = stale_time
    count = proposal_expiry.sweep_expired(max_age_hours=72)
    assert count == 1
    assert proposal_store.get_proposal(p1["proposal_id"])["status"] == ProposalStatus.EXPIRED.value


def test_sweep_does_not_touch_resolved_proposals():
    p1 = _save(agent="churn_prevention", store_id="s3", proposal_type="DRAFT_CHURN_CAMPAIGN")
    proposal_store.resolve_proposal(p1["proposal_id"], ProposalStatus.REJECTED.value, "no")
    stale_time = (datetime.now(timezone.utc) - timedelta(hours=200)).isoformat()
    proposal_store._by_id[p1["proposal_id"]]["created_at"] = stale_time
    proposal_expiry.sweep_expired(max_age_hours=72)
    assert proposal_store.get_proposal(p1["proposal_id"])["status"] == ProposalStatus.REJECTED.value
