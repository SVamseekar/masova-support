"""Sweeps stale PENDING proposals to EXPIRED after a configurable age."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from masova_agent.runtime import proposal_store
from masova_agent.runtime.models import ProposalStatus


def sweep_expired(max_age_hours: int = 72) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    count = 0
    for proposal in proposal_store.list_proposals(limit=500):
        if str(proposal.get("status")) != ProposalStatus.PENDING.value:
            continue
        created_raw = proposal.get("created_at") or ""
        try:
            created_at = datetime.fromisoformat(str(created_raw).replace("Z", "+00:00"))
        except ValueError:
            continue
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if created_at < cutoff:
            proposal_store.resolve_proposal(
                proposal["proposal_id"],
                ProposalStatus.EXPIRED.value,
                note="expired after 72h",
            )
            count += 1
    return count
