"""
Integration tests that make REAL HTTP calls to BACKEND_URL. Excluded from the
default test run (see pyproject.toml addopts). Run explicitly:

    RUN_INTEGRATION_TESTS=1 BACKEND_URL=http://192.168.50.88:8080 \\
      AGENT_TOKEN=<ops token> pytest -m integration

Requires a real, reachable backend and valid auth — see
docs/backend-connectivity-verification-spec.md.

These tests distinguish "endpoint exists and responded" from "404/400 because
the path is wrong." They do not assert business data. POST purchase-order
drafts are extra-gated (TEST_LIVE_WRITES=1) so a default integration run
cannot create Java-side drafts.
"""

import os

import pytest

pytestmark = pytest.mark.integration

skip_reason = "Set RUN_INTEGRATION_TESTS=1 and a real BACKEND_URL to run against a live backend"


def _not_missing_path(result: dict) -> None:
    assert isinstance(result, dict)
    err = str(result.get("error") or "")
    assert "http_404" not in err
    assert "http_400" not in err
    if result.get("ok") is False:
        pytest.fail(f"backend rejected the contract path: {result}")


@pytest.fixture(autouse=True)
def _require_opt_in():
    if os.getenv("RUN_INTEGRATION_TESTS") != "1":
        pytest.skip(skip_reason)
    if not os.getenv("AGENT_TOKEN"):
        pytest.skip("AGENT_TOKEN is required for live ops_tools calls")


@pytest.mark.asyncio
async def test_demand_forecast_endpoint_does_not_404():
    from masova_agent.tools import ops_tools

    result = await ops_tools.get_forecast_snippet(store_id=os.getenv("TEST_STORE_ID", "DOM001"))
    _not_missing_path(result)
    assert result.get("ok") is True
    assert "forecasts" in result


@pytest.mark.asyncio
async def test_top_products_endpoint_does_not_404():
    from masova_agent.tools import ops_tools

    result = await ops_tools.get_top_items(store_id=os.getenv("TEST_STORE_ID", "DOM001"))
    _not_missing_path(result)
    assert result.get("ok") is True


@pytest.mark.asyncio
async def test_kitchen_metrics_endpoint_does_not_404():
    from masova_agent.tools import ops_tools

    result = await ops_tools.read_kitchen_metrics(
        store_id=os.getenv("TEST_STORE_ID", "DOM001"), staff_id=None, date="2026-09-11"
    )
    _not_missing_path(result)
    assert result.get("ok") is True


@pytest.mark.asyncio
async def test_draft_po_endpoint_does_not_404():
    if os.getenv("TEST_LIVE_WRITES") != "1":
        pytest.skip("Set TEST_LIVE_WRITES=1 to POST a DRAFT purchase order")
    from masova_agent.tools import ops_tools

    result = await ops_tools.create_draft_po(
        store_id=os.getenv("TEST_STORE_ID", "DOM001"),
        supplier_id=os.getenv("TEST_SUPPLIER_ID", "SUP-TEST"),
        items=[
            {
                "inventory_item_id": "ITEM-TEST",
                "item_name": "connectivity-check",
                "quantity": 1,
            }
        ],
        rationale="integration contract check — discard if created",
    )
    _not_missing_path(result)
