"""
Unit tests for Agent 1 backend tool functions.
All HTTP calls are mocked — no live backend required.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_get(status_code: int, json_body: dict):
    """Return a mock httpx response for _get calls."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body
    resp.raise_for_status = MagicMock(
        side_effect=None if status_code < 400 else Exception(f"HTTP {status_code}")
    )
    return resp


def _mock_post(status_code: int, json_body: dict):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body
    resp.raise_for_status = MagicMock(
        side_effect=None if status_code < 400 else Exception(f"HTTP {status_code}")
    )
    return resp


# ---------------------------------------------------------------------------
# get_order_status
# ---------------------------------------------------------------------------

class TestGetOrderStatus:
    def test_known_order_returns_status(self):
        from masova_agent.tools.backend_tools import get_order_status
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_get(200, {
                "status": "PREPARING",
                "orderNumber": "ORD-001",
                "items": [{"quantity": 2, "name": "Chicken Biryani"}],
                "preparationTime": 15,
            })
            result = get_order_status("ORD-001")
        assert "ORD-001" in result
        assert "kitchen" in result.lower() or "prepar" in result.lower()
        assert "Chicken Biryani" in result

    def test_unknown_order_returns_friendly_message(self):
        from masova_agent.tools.backend_tools import get_order_status
        from httpx import HTTPStatusError, Request, Response
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.side_effect = HTTPStatusError(
                "404", request=MagicMock(), response=MagicMock(status_code=404)
            )
            mock_resp.status_code = 404
            mock_get.return_value = mock_resp
            result = get_order_status("ORD-MISSING")
        assert "couldn't find" in result.lower() or "error" in result.lower()

    def test_delivered_order(self):
        from masova_agent.tools.backend_tools import get_order_status
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_get(200, {
                "status": "DELIVERED",
                "orderNumber": "ORD-002",
                "items": [],
            })
            result = get_order_status("ORD-002")
        assert "delivered" in result.lower()

    def test_cancelled_order(self):
        from masova_agent.tools.backend_tools import get_order_status
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_get(200, {
                "status": "CANCELLED",
                "orderNumber": "ORD-003",
                "items": [],
            })
            result = get_order_status("ORD-003")
        assert "cancelled" in result.lower()


# ---------------------------------------------------------------------------
# get_menu_items
# ---------------------------------------------------------------------------

class TestGetMenuItems:
    def test_returns_formatted_items(self):
        from masova_agent.tools.backend_tools import get_menu_items
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_get(200, {
                "content": [
                    {"name": "Masala Dosa", "basePrice": 120, "spiceLevel": "MEDIUM"},
                    {"name": "Filter Coffee", "basePrice": 60},
                ]
            })
            result = get_menu_items("store-1")
        assert "Masala Dosa" in result
        assert "₹120" in result
        assert "Filter Coffee" in result

    def test_category_filter_passed(self):
        from masova_agent.tools.backend_tools import get_menu_items
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_get(200, {"content": []})
            get_menu_items("store-1", category="biryani")
            # params is always passed as a keyword argument by _get()
            params = mock_get.call_args.kwargs.get("params", {})
            assert params.get("category") == "BIRYANI"

    def test_empty_menu_returns_friendly_message(self):
        from masova_agent.tools.backend_tools import get_menu_items
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_get(200, {"content": []})
            result = get_menu_items("store-1")
        assert "no menu" in result.lower() or "not found" in result.lower()

    def test_api_error_returns_friendly_message(self):
        from masova_agent.tools.backend_tools import get_menu_items
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
            mock_get.side_effect = Exception("Connection refused")
            result = get_menu_items("store-1")
        assert "couldn't" in result.lower() or "error" in result.lower()


# ---------------------------------------------------------------------------
# get_store_hours
# ---------------------------------------------------------------------------

class TestGetStoreHours:
    def test_open_store(self):
        from masova_agent.tools.backend_tools import get_store_hours
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_get(200, {
                "name": "MaSoVa Jubilee Hills",
                "isOpen": True,
                "openingTime": "09:00",
                "closingTime": "22:00",
            })
            result = get_store_hours("store-1")
        assert "OPEN" in result
        assert "09:00" in result
        assert "22:00" in result

    def test_closed_store(self):
        from masova_agent.tools.backend_tools import get_store_hours
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_get(200, {
                "name": "MaSoVa Banjara Hills",
                "isOpen": False,
                "openingTime": "10:00",
                "closingTime": "23:00",
            })
            result = get_store_hours("store-2")
        assert "CLOSED" in result

    def test_api_error(self):
        from masova_agent.tools.backend_tools import get_store_hours
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
            mock_get.side_effect = Exception("timeout")
            result = get_store_hours("store-1")
        assert "couldn't" in result.lower() or "error" in result.lower()


# ---------------------------------------------------------------------------
# submit_complaint
# ---------------------------------------------------------------------------

class TestSubmitComplaint:
    def test_valid_complaint_returns_ticket(self):
        from masova_agent.tools.backend_tools import submit_complaint
        with patch("masova_agent.tools.backend_tools.httpx.post") as mock_post:
            mock_post.return_value = _mock_post(201, {"id": "TKT-999"})
            result = submit_complaint("CUST-1", "ORD-001", "Food was cold and arrived late")
        assert "TKT-999" in result or "submitted" in result.lower()

    def test_short_description_rejected(self):
        from masova_agent.tools.backend_tools import submit_complaint
        result = submit_complaint("CUST-1", "ORD-001", "bad")
        assert "more detail" in result.lower() or "provide" in result.lower()

    def test_api_failure_gives_fallback_message(self):
        from masova_agent.tools.backend_tools import submit_complaint
        with patch("masova_agent.tools.backend_tools.httpx.post") as mock_post:
            mock_post.side_effect = Exception("timeout")
            result = submit_complaint("CUST-1", "ORD-001", "The food was completely wrong order")
        assert "noted" in result.lower() or "support" in result.lower()


# ---------------------------------------------------------------------------
# get_loyalty_points
# ---------------------------------------------------------------------------

class TestGetLoyaltyPoints:
    def test_gold_member(self):
        from masova_agent.tools.backend_tools import get_loyalty_points
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_get(200, {
                "loyaltyPoints": 3200,
                "loyaltyTier": "GOLD",
            })
            result = get_loyalty_points("CUST-1")
        assert "3200" in result
        assert "GOLD" in result
        assert "PLATINUM" in result  # next tier shown

    def test_platinum_member_max_tier_message(self):
        from masova_agent.tools.backend_tools import get_loyalty_points
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_get(200, {
                "loyaltyPoints": 12000,
                "loyaltyTier": "PLATINUM",
            })
            result = get_loyalty_points("CUST-1")
        assert "PLATINUM" in result
        assert "highest" in result.lower()

    def test_api_error(self):
        from masova_agent.tools.backend_tools import get_loyalty_points
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
            mock_get.side_effect = Exception("timeout")
            result = get_loyalty_points("CUST-1")
        assert "couldn't" in result.lower() or "error" in result.lower()


# ---------------------------------------------------------------------------
# get_store_wait_time
# ---------------------------------------------------------------------------

class TestGetStoreWaitTime:
    def test_empty_kitchen(self):
        from masova_agent.tools.backend_tools import get_store_wait_time
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_get(200, {"totalElements": 0})
            result = get_store_wait_time("store-1")
        assert "free" in result.lower() or "fast" in result.lower()

    def test_busy_kitchen(self):
        from masova_agent.tools.backend_tools import get_store_wait_time
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_get(200, {"totalElements": 12})
            result = get_store_wait_time("store-1")
        assert "busy" in result.lower() or "40" in result

    def test_moderate_kitchen(self):
        from masova_agent.tools.backend_tools import get_store_wait_time
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_get(200, {"totalElements": 7})
            result = get_store_wait_time("store-1")
        assert "25" in result or "moderate" in result.lower() or "busy" in result.lower()


# ---------------------------------------------------------------------------
# cancel_order
# ---------------------------------------------------------------------------

class TestCancelOrder:
    def test_cancellable_order(self):
        from masova_agent.tools.backend_tools import cancel_order
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get, \
             patch("masova_agent.tools.backend_tools.httpx.post") as mock_post:
            mock_get.return_value = _mock_get(200, {"status": "RECEIVED"})
            mock_post.return_value = _mock_post(200, {"status": "CANCELLED"})
            result = cancel_order("ORD-001", "Changed my mind")
        assert "cancelled" in result.lower()

    def test_order_already_preparing_cannot_cancel(self):
        from masova_agent.tools.backend_tools import cancel_order
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_get(200, {"status": "PREPARING"})
            result = cancel_order("ORD-002", "Changed my mind")
        assert "cannot be cancelled" in result.lower() or "already" in result.lower()

    def test_short_reason_rejected(self):
        from masova_agent.tools.backend_tools import cancel_order
        result = cancel_order("ORD-001", "no")
        assert "reason" in result.lower()


# ---------------------------------------------------------------------------
# request_refund
# ---------------------------------------------------------------------------

class TestRequestRefund:
    def test_valid_refund_request(self):
        from masova_agent.tools.backend_tools import request_refund
        with patch("masova_agent.tools.backend_tools.httpx.post") as mock_post:
            mock_post.return_value = _mock_post(201, {"refundId": "REF-123"})
            result = request_refund("ORD-001", "Wrong items delivered")
        assert "REF-123" in result or "refund" in result.lower()

    def test_short_reason_rejected(self):
        from masova_agent.tools.backend_tools import request_refund
        result = request_refund("ORD-001", "bad")
        assert "reason" in result.lower()

    def test_api_error_gives_fallback(self):
        from masova_agent.tools.backend_tools import request_refund
        with patch("masova_agent.tools.backend_tools.httpx.post") as mock_post:
            mock_post.side_effect = Exception("timeout")
            result = request_refund("ORD-001", "Completely wrong order received")
        assert "3" in result or "days" in result.lower() or "logged" in result.lower()
