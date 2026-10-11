"""HTTP path contracts for ops tools against the live Java gateway."""

from unittest.mock import AsyncMock, patch

import pytest
import httpx

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


@pytest.mark.asyncio
async def test_read_kitchen_metrics_uses_orders_analytics_with_staff_and_date():
    with patch.object(ops_tools, "get_json", new=AsyncMock(return_value=(200, {}))) as mock_get:
        await ops_tools.read_kitchen_metrics(store_id="s1", staff_id="staff1", date="2026-09-11")
        called_path = mock_get.call_args[0][1]
        params = mock_get.call_args.kwargs.get("params") or {}
        assert "/api/orders/analytics" in called_path
        assert params.get("type") == "kitchen"
        assert params.get("staffId") == "staff1"


@pytest.mark.asyncio
async def test_read_kitchen_metrics_falls_back_without_staff_id():
    with patch.object(ops_tools, "get_json", new=AsyncMock(return_value=(200, {}))) as mock_get:
        await ops_tools.read_kitchen_metrics(store_id="s1", staff_id=None, date="2026-09-11")
        params = mock_get.call_args.kwargs.get("params") or {}
        assert params.get("type") != "kitchen"
        assert params.get("type") == "prep-time"


@pytest.mark.asyncio
async def test_get_top_items_uses_analytics_top_products_type():
    with patch.object(
        ops_tools, "get_json", new=AsyncMock(return_value=(200, {"items": []}))
    ) as mock_get:
        await ops_tools.get_top_items(store_id="s1")
        called_path = mock_get.call_args[0][1]
        params = mock_get.call_args.kwargs.get("params") or {}
        assert called_path.endswith("/api/analytics")
        assert params.get("type") == "top-products"
        assert "/api/analytics/products" not in called_path


@pytest.mark.asyncio
async def test_churn_prevention_creates_no_campaign_on_empty_result(monkeypatch):
    from masova_agent.agents import churn_prevention_agent

    monkeypatch.delenv("AGENT_TOKEN", raising=False)
    result = await churn_prevention_agent.run_churn_prevention()
    assert result is not None


@pytest.mark.asyncio
async def test_low_stock_outage_is_not_a_successful_empty_assessment():
    with patch.object(
        ops_tools,
        "get_json",
        new=AsyncMock(side_effect=[(200, [{"id": "s1"}]), (503, {})]),
    ):
        result = await ops_tools.list_low_stock()
    assert result["ok"] is False
    assert result["error"] == "inventory_unavailable"
    assert result["failed_store_ids"] == ["s1"]
    assert result["items"] == []


@pytest.mark.asyncio
async def test_low_stock_partial_coverage_preserves_zero_stock_and_reports_failed_store():
    with patch.object(
        ops_tools,
        "get_json",
        new=AsyncMock(
            side_effect=[
                (200, [{"id": "s1"}, {"id": "s2"}]),
                (
                    200,
                    [
                        {
                            "id": "item1",
                            "currentStock": 0,
                            "quantity": 99,
                            "minimumStock": 0,
                            "minStock": 9,
                        }
                    ],
                ),
                (403, {}),
            ]
        ),
    ):
        result = await ops_tools.list_low_stock()
    assert result["ok"] is False
    assert result["failed_store_ids"] == ["s2"]
    assert result["count"] == 1
    assert result["items"][0]["current_stock"] == 0
    assert result["items"][0]["minimum_stock"] == 0


@pytest.mark.asyncio
async def test_low_stock_verified_empty_inventory_is_successful():
    with patch.object(ops_tools, "get_json", new=AsyncMock(return_value=(200, []))):
        result = await ops_tools.list_low_stock("s1")
    assert result == {"ok": True, "items": [], "count": 0}


@pytest.mark.asyncio
async def test_low_stock_transport_failure_retains_completed_store_data():
    with patch.object(
        ops_tools,
        "get_json",
        new=AsyncMock(
            side_effect=[
                (200, [{"id": "s1"}, {"id": "s2"}]),
                (200, [{"id": "item1", "currentStock": 0}]),
                httpx.ConnectError("unavailable"),
            ]
        ),
    ):
        result = await ops_tools.list_low_stock()
    assert result["ok"] is False
    assert result["failed_store_ids"] == ["s2"]
    assert result["count"] == 1
    assert result["items"][0]["id"] == "item1"
