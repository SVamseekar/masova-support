"""Manager copilot agent allowlist and run contract."""

import pytest

from masova_agent.agents.manager_chat_agent import run_manager_chat
from masova_agent.runtime.wrap import AGENT_ALLOWLISTS
from masova_agent.runtime.policy import DEFAULT_TOOL_REGISTRY, RiskTier


def test_manager_chat_has_allowlist_entry():
    assert "manager_chat" in AGENT_ALLOWLISTS
    assert len(AGENT_ALLOWLISTS["manager_chat"]) >= 2


def test_manager_chat_allowlist_has_no_execute_tools():
    for tool_name in AGENT_ALLOWLISTS["manager_chat"]:
        risk = DEFAULT_TOOL_REGISTRY.get(tool_name)
        if risk is not None:
            assert risk.tier != RiskTier.EXECUTE


@pytest.mark.asyncio
async def test_run_manager_chat_returns_reply_for_low_stock_query():
    result = await run_manager_chat(
        "what's low on stock at store s1?", session_id="sess1", store_id="s1"
    )
    assert "reply" in result
    assert isinstance(result["reply"], str)


@pytest.mark.asyncio
async def test_run_manager_chat_multi_turn_persists_session(monkeypatch):
    r1 = await run_manager_chat("hello", session_id="sess2")
    r2 = await run_manager_chat("what did I just say?", session_id="sess2")
    assert r1["session_id"] == r2["session_id"] == "sess2"
