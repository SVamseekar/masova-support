"""HTTP path contracts for ops tools against the live Java gateway."""

from unittest.mock import AsyncMock, patch

import pytest

from masova_agent.tools import ops_tools


@pytest.fixture(autouse=True)
def _token(monkeypatch):
    monkeypatch.setenv("AGENT_TOKEN", "test-token")


@pytest.mark.asyncio
async def test_get_forecast_snippet_calls_bi_endpoint():
    with patch.object(
        ops_tools, "get_json", new=AsyncMock(return_value=(200, {"forecasts": []}))
    ) as mock_get:
        await ops_tools.get_forecast_snippet(store_id="s1")
        called_path = mock_get.call_args[0][1]
        params = mock_get.call_args.kwargs.get("params") or {}
        assert "/api/bi" in called_path
        assert params.get("type") == "demand-forecast"
        assert "/api/analytics/forecast" not in called_path


@pytest.mark.asyncio
async def test_write_forecast_no_longer_posts_nonexistent_endpoint():
    with patch.object(ops_tools, "post_json", new=AsyncMock()) as mock_post:
        await ops_tools.write_forecast(store_id="s1", forecasts=[{"hour": 1, "qty": 2}])
        mock_post.assert_not_called()


@pytest.mark.asyncio
async def test_create_draft_po_posts_entity_not_auto_generate():
    with patch.object(
        ops_tools, "post_json", new=AsyncMock(return_value=(201, {"id": "po1", "status": "DRAFT"}))
    ) as mock_post:
        await ops_tools.create_draft_po(
            store_id="s1", supplier_id="sup1", items=[{"sku": "x", "qty": 10, "quantity": 10}]
        )
        called_path = mock_post.call_args[0][1]
        payload = mock_post.call_args[0][2]
        assert called_path.endswith("/api/purchase-orders")
        assert "auto-generate" not in called_path
        assert payload.get("status") == "DRAFT"
