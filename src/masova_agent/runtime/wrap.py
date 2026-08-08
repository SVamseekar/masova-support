"""Helpers for ops agents to run through AgentRuntime with rule fallbacks."""

from __future__ import annotations

from typing import Any, Optional

from .agent_runtime import get_runtime
from .models import AgentRunRequest, FallbackFn, LlmRunnerFn


# Default tool allowlists per agent (no EXECUTE).
AGENT_ALLOWLISTS: dict[str, list[str]] = {
    "support_chat": [
        "get_order_status",
        "get_menu_items",
        "get_store_hours",
        "get_loyalty_points",
        "get_store_wait_time",
        "submit_complaint",
        "cancel_order",
        "request_refund",
    ],
    "demand_forecast": ["compute_wma_forecast", "write_forecast", "read_order_metrics"],
    "inventory_reorder": [
        "read_inventory_levels",
        "compute_wma_forecast",
        "draft_purchase_order",
    ],
    "churn_prevention": ["read_order_metrics", "draft_churn_campaign"],
    "review_response": ["draft_review_reply", "read_order_metrics"],
    "shift_optimisation": ["read_staff_slots", "draft_shift_roster", "compute_wma_forecast"],
    "kitchen_coach": ["read_kitchen_metrics", "draft_kitchen_brief"],
    "dynamic_pricing": ["read_order_metrics", "suggest_price_adjustment"],
}


async def run_ops_agent(
    agent_name: str,
    trigger_type: str,
    fallback: FallbackFn,
    *,
    store_id: Optional[str] = None,
    goal: str = "",
    context: Optional[dict[str, Any]] = None,
    llm_runner: Optional[LlmRunnerFn] = None,
    prefer_llm: bool = False,
) -> dict[str, Any]:
    """
    Run an ops agent through the shared runtime.

    prefer_llm defaults False for ops until LLM runners are injected — rule
    fallback is the production path; when prefer_llm=True and llm_runner is
    set, LLM is tried first.
    """
    request = AgentRunRequest(
        agent_name=agent_name,
        trigger_type=trigger_type,
        store_id=store_id,
        goal=goal or f"Run {agent_name}",
        context=context or {},
        allowed_tools=list(AGENT_ALLOWLISTS.get(agent_name, [])),
        fallback=fallback,
        llm_runner=llm_runner,
        prefer_llm=prefer_llm and llm_runner is not None,
    )
    result = await get_runtime().run(request)
    # Preserve legacy agent response shape for HTTP triggers + tests
    payload = dict(result.output) if result.output else {}
    if result.status == "error" and result.error and "error" not in payload:
        payload["error"] = result.error
    if "status" not in payload and result.status == "ok":
        payload.setdefault("status", "ok")
    payload["_runtime"] = {
        "run_id": result.run_id,
        "agent_name": result.agent_name,
        "trigger_type": result.trigger_type,
        "used_fallback": result.used_fallback,
        "latency_ms": result.latency_ms,
        "proposal_count": len(result.proposals),
        "proposals": [p.to_dict() for p in result.proposals],
        "summary": result.summary,
        "status": result.status,
    }
    return payload
