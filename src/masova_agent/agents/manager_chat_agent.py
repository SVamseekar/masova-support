"""Manager conversational copilot: read/compute/propose tools over ops agents plus SOP RAG.

EXECUTE-tier tools are never registered here — see runtime/policy.py's blocklist.
"""

from __future__ import annotations

from typing import Any, Optional

from masova_agent.knowledge.rag import search_ops_manual as _search_ops_manual_sync
from masova_agent.runtime.guardrails import screen_input, screen_output
from masova_agent.runtime.ops_llm import make_ops_llm_runner, ops_prefer_llm
from masova_agent.runtime import proposal_store
from masova_agent.tools import ops_tools
from masova_agent.agents import (
    churn_prevention_agent,
    demand_forecasting_agent,
    dynamic_pricing_agent,
    inventory_reorder_agent,
    kitchen_coach_agent,
    review_response_agent,
    shift_optimisation_agent,
)

MANAGER_INSTRUCTION = """You are MaSoVa's manager copilot (ops).

Help managers with inventory, forecasts, staffing, kitchen metrics, pricing,
churn, reviews, and SOP lookups. Use tools for all numbers. Never claim you
executed a write — proposals require manager approval. Never call EXECUTE-tier
tools (none are available).
"""


async def search_ops_manual(query: str, top_k: int = 3) -> dict[str, Any]:
    results = _search_ops_manual_sync(query, top_k=top_k)
    return {"ok": True, "results": results}


async def list_manager_proposals(
    store_id: Optional[str] = None,
    status: Optional[str] = None,
    agent: Optional[str] = None,
    limit: int = 50,
) -> dict[str, Any]:
    rows = proposal_store.list_proposals(store_id=store_id, status=status, agent=agent, limit=limit)
    return {"ok": True, "proposals": rows}


async def resolve_manager_proposal(proposal_id: str, status: str, note: str = "") -> dict[str, Any]:
    rec = proposal_store.resolve_proposal(proposal_id, status, note=note)
    if rec is None:
        return {"ok": False, "error": "proposal not found"}
    return {"ok": True, "proposal": rec}


MANAGER_TOOL_FUNCTIONS: dict[str, Any] = {
    "list_stores": ops_tools.list_stores,
    "list_low_stock": ops_tools.list_low_stock,
    "count_active_orders": ops_tools.count_active_orders,
    "count_recent_orders": ops_tools.count_recent_orders,
    "get_forecast_snippet": ops_tools.get_forecast_snippet,
    "get_top_items": ops_tools.get_top_items,
    "compute_pricing_signal": ops_tools.compute_pricing_signal,
    "get_order_context": ops_tools.get_order_context,
    "read_kitchen_metrics": ops_tools.read_kitchen_metrics,
    "read_order_metrics": ops_tools.read_order_metrics,
    "notify_managers": ops_tools.notify_managers,
    "run_demand_forecast": demand_forecasting_agent.run_demand_forecast,
    "run_inventory_reorder": inventory_reorder_agent.run_inventory_reorder,
    "run_churn_prevention": churn_prevention_agent.run_churn_prevention,
    "run_shift_optimisation": shift_optimisation_agent.run_shift_optimisation,
    "run_kitchen_coach": kitchen_coach_agent.run_kitchen_coach,
    "run_dynamic_pricing": dynamic_pricing_agent.run_dynamic_pricing,
    "run_review_response": review_response_agent.draft_review_response,
    "list_manager_proposals": list_manager_proposals,
    "resolve_manager_proposal": resolve_manager_proposal,
    "search_ops_manual": search_ops_manual,
}

MANAGER_TOOL_NAMES = list(MANAGER_TOOL_FUNCTIONS.keys())


def _bind_allowlist() -> None:
    from masova_agent.runtime.wrap import AGENT_ALLOWLISTS

    AGENT_ALLOWLISTS["manager_chat"] = list(MANAGER_TOOL_NAMES)


_bind_allowlist()


def _manager_llm_runner():
    schemas = {
        name: {
            "description": f"Manager copilot tool {name}",
            "parameters": {"type": "object", "properties": {}},
        }
        for name in MANAGER_TOOL_NAMES
    }
    return make_ops_llm_runner(
        instruction=MANAGER_INSTRUCTION,
        tool_names=MANAGER_TOOL_NAMES,
        tool_functions=MANAGER_TOOL_FUNCTIONS,
        tool_schemas=schemas,
    )


async def run_manager_chat(message: str, session_id: str, store_id: str | None = None) -> dict:
    screened_text, blocked = screen_input(message)
    if blocked:
        return {"reply": "I can't help with that request.", "session_id": session_id}

    from masova_agent.runtime.wrap import run_ops_agent

    async def _fallback(_req=None):
        return {
            "status": "ok",
            "reply": (
                "I can help with inventory, forecasts, staffing, kitchen metrics, "
                "pricing, and SOP lookups. What do you need?"
            ),
            "summary": "manager_chat_fallback",
        }

    prefer = ops_prefer_llm()
    payload = await run_ops_agent(
        "manager_chat",
        "chat",
        _fallback,
        store_id=store_id,
        goal=screened_text[:500],
        context={"session_id": session_id, "store_id": store_id},
        llm_runner=_manager_llm_runner() if prefer else None,
        prefer_llm=prefer,
        allowed_tools=MANAGER_TOOL_NAMES,
    )
    reply = str(payload.get("reply") or payload.get("summary") or "").strip()
    if not reply:
        fb = await _fallback()
        reply = str(fb["reply"])
    return {"reply": screen_output(reply), "session_id": session_id}
