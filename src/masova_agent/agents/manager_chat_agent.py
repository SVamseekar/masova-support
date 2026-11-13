"""Manager conversational copilot: read/compute/propose tools over ops agents plus SOP RAG.

EXECUTE-tier tools are never registered here — see runtime/policy.py's blocklist.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import asyncio
from collections import OrderedDict
from functools import wraps
from typing import Any, Optional

from .manager_audio import transcribe_manager_audio, synthesize_manager_reply

from masova_agent.knowledge.rag import search_ops_manual as _search_ops_manual_sync
from masova_agent.runtime.guardrails import screen_input
from masova_agent.runtime.ops_llm import make_ops_llm_runner, ops_prefer_llm
from masova_agent.runtime import proposal_store, conversation_store
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

Use public tool results as evidence. Do not expose private reasoning or raw personal data.
The selected store limits read tools. Specialist runners are all-store operations unless
their schema explicitly takes a review store. Do not imply an all-store run is store-scoped.
Decisions are recorded only through explicit manager review controls; approval does not execute.
Answer only restaurant operations questions. Keep replies concise and disclose unavailable tools.
"""

_HISTORY: OrderedDict[str, list[dict[str, str]]] = OrderedDict()


async def search_ops_manual(query: str, top_k: int = 3) -> dict[str, Any]:
    results = await asyncio.to_thread(_search_ops_manual_sync, query, top_k=top_k)
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
    "search_ops_manual": search_ops_manual,
}

MANAGER_TOOL_NAMES = list(MANAGER_TOOL_FUNCTIONS.keys())


def _bind_allowlist() -> None:
    from masova_agent.runtime.wrap import AGENT_ALLOWLISTS

    AGENT_ALLOWLISTS["manager_chat"] = list(MANAGER_TOOL_NAMES)


_bind_allowlist()


def _tool_schema(fn: Any) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, param in inspect.signature(fn).parameters.items():
        annotation = str(param.annotation)
        kind = "object" if "dict" in annotation.lower() else "string"
        if annotation in ("int", "<class 'int'>"):
            kind = "integer"
        properties[name] = {"type": kind}
        if name == "review_data":
            properties[name] = {
                "type": "object",
                "properties": {
                    "storeId": {"type": "string"},
                    "reviewId": {"type": "string"},
                    "orderId": {"type": "string"},
                    "rating": {"type": "integer"},
                    "text": {"type": "string"},
                },
                "required": ["storeId", "reviewId", "rating", "text"],
            }
        if param.default is inspect.Parameter.empty:
            required.append(name)
    return {
        "description": fn.__doc__ or fn.__name__,
        "parameters": {"type": "object", "properties": properties, "required": required},
    }


def _manager_llm_runner(store_id: str | None = None, scopes: list[str] | None = None):
    scopes = scopes if scopes is not None else ["*"]
    functions: dict[str, Any] = {}
    for name, fn in MANAGER_TOOL_FUNCTIONS.items():
        needed_scope = "chat:manager"
        if name.startswith("run_"):
            needed_scope = "trigger:" + name.removeprefix("run_")
            # Existing specialists loop every store. No selected-store execution claims.
            if store_id:
                continue
        elif name == "list_manager_proposals":
            needed_scope = "read:proposals"
        elif name == "list_stores":
            needed_scope = "read:registry"
        elif name == "notify_managers":
            # Notifications remain specialist-owned; chat never sends arbitrary messages.
            continue
        elif name == "get_order_context" and store_id:
            # Order lookup lacks a store constraint. Use selected-store metrics instead.
            continue
        if "*" not in scopes and needed_scope not in scopes:
            continue
        if store_id and "store_id" in inspect.signature(fn).parameters:

            @wraps(fn)
            async def scoped_tool(_fn=fn, **kwargs):
                kwargs["store_id"] = store_id
                return await _fn(**kwargs)

            functions[name] = scoped_tool
        else:
            functions[name] = fn
    schemas = {name: _tool_schema(MANAGER_TOOL_FUNCTIONS[name]) for name in functions}
    runner = make_ops_llm_runner(
        instruction=MANAGER_INSTRUCTION,
        tool_names=list(functions),
        tool_functions=functions,
        tool_schemas=schemas,
    )

    async def scoped_runner(request):
        request.allowed_tools = list(functions)
        return await runner(request)

    return scoped_runner


async def run_manager_chat(
    message: str,
    session_id: str,
    store_id: str | None = None,
    *,
    audio_base64: str | None = None,
    mime_type: str = "audio/webm",
    scopes: list[str] | None = None,
    principal: str = "manager",
) -> dict:
    import base64

    transcript = ""
    if audio_base64 and not message.strip():
        transcript = await transcribe_manager_audio(base64.b64decode(audio_base64), mime_type)
        message = transcript
    screened_text, blocked = screen_input(message)
    screened_text = conversation_store.public_text(screened_text, principal)
    if transcript:
        transcript = conversation_store.public_text(transcript, principal)
    if blocked:
        return {
            "reply": "I can't help with that request.",
            "session_id": session_id,
            "sessionId": session_id,
            "transcript": transcript,
            "blocked": True,
        }

    from masova_agent.runtime.wrap import run_ops_agent

    async def _fallback(_req=None):
        return {
            "status": "ok",
            "reply": (
                "Manager copilot is unavailable. Use the specialist controls to request "
                "an operations run, or review existing records. Specialist runs cover all stores."
            ),
            "summary": "manager_chat_fallback",
        }

    prefer = ops_prefer_llm()
    history_key = hashlib.sha256(
        json.dumps([principal, session_id, store_id or ""]).encode()
    ).hexdigest()
    history = list(_HISTORY.get(history_key, []))
    try:
        history = await asyncio.to_thread(
            conversation_store.load_context, principal, store_id, session_id
        )
    except conversation_store.HistoryUnavailable:
        pass  # Existing bounded process context remains available; persistence status is explicit.
    runner = _manager_llm_runner(store_id, scopes) if prefer else None
    payload = await run_ops_agent(
        "manager_chat",
        "chat",
        _fallback,
        store_id=store_id,
        goal=screened_text[:500],
        context={"session_id": session_id, "store_id": store_id, "history": history},
        llm_runner=runner,
        prefer_llm=prefer,
        allowed_tools=MANAGER_TOOL_NAMES,
    )
    reply = str(payload.get("reply") or payload.get("summary") or "").strip()
    if not reply:
        fb = await _fallback()
        reply = str(fb["reply"])
    reply = conversation_store.public_text(reply, principal)
    _HISTORY[history_key] = (
        history
        + [
            {"role": "user", "text": screened_text[:2000]},
            {"role": "assistant", "text": reply[:2000]},
        ]
    )[-10:]
    _HISTORY.move_to_end(history_key)
    while len(_HISTORY) > 128:
        _HISTORY.popitem(last=False)
    saved = True
    try:
        await asyncio.to_thread(
            conversation_store.append_exchange,
            principal,
            store_id,
            session_id,
            screened_text,
            reply,
        )
    except conversation_store.HistoryUnavailable:
        saved = False
    runtime = payload.get("_runtime") or {}
    result = {
        "reply": reply,
        "session_id": session_id,
        "sessionId": session_id,
        "storeId": store_id,
        "transcript": transcript,
        "run_id": runtime.get("run_id"),
        "tools_used": runtime.get("tools_used") or [],
        "proposals": runtime.get("proposals") or [],
        "used_fallback": bool(runtime.get("used_fallback")),
        "historySaved": saved,
    }
    if not saved:
        result["historyError"] = "Conversation history unavailable. This response was not saved."
    if audio_base64:
        try:
            result.update(await synthesize_manager_reply(reply))
        except Exception:
            result["audioError"] = "Speech unavailable. Text reply preserved."
    return result
