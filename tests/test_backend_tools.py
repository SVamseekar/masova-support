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


def _tool_context(customer_id):
    """Minimal stand-in for ADK's ToolContext — only `.state` is touched by
    backend_tools._session_customer_id(). Real ADK ToolContext construction
    requires a full InvocationContext, which is unnecessary for these unit
    tests."""
    ctx = MagicMock()
    ctx.state = {"customer_id": customer_id}
    return ctx


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
            result = get_order_status("ORD-001", _tool_context("CUST-1"))
        assert "ORD-001" in result
        assert "kitchen" in result.lower() or "prepar" in result.lower()
        assert "Chicken Biryani" in result

    def test_unknown_order_returns_friendly_message(self):
        from masova_agent.tools.backend_tools import get_order_status
        from httpx import HTTPStatusError
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.side_effect = HTTPStatusError(
                "404", request=MagicMock(), response=MagicMock(status_code=404)
            )
            mock_resp.status_code = 404
            mock_get.return_value = mock_resp
            result = get_order_status("ORD-MISSING", _tool_context("CUST-1"))
        assert "couldn't find" in result.lower() or "error" in result.lower()

    def test_delivered_order(self):
        from masova_agent.tools.backend_tools import get_order_status
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_get(200, {
                "status": "DELIVERED",
                "orderNumber": "ORD-002",
                "items": [],
            })
            result = get_order_status("ORD-002", _tool_context("CUST-1"))
        assert "delivered" in result.lower()

    def test_cancelled_order(self):
        from masova_agent.tools.backend_tools import get_order_status
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_get(200, {
                "status": "CANCELLED",
                "orderNumber": "ORD-003",
                "items": [],
            })
            result = get_order_status("ORD-003", _tool_context("CUST-1"))
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
            result = submit_complaint("CUST-1", "ORD-001", "Food was cold and arrived late", _tool_context("CUST-1"))
        assert "TKT-999" in result or "submitted" in result.lower()

    def test_short_description_rejected(self):
        from masova_agent.tools.backend_tools import submit_complaint
        result = submit_complaint("CUST-1", "ORD-001", "bad", _tool_context("CUST-1"))
        assert "more detail" in result.lower() or "provide" in result.lower()

    def test_api_failure_gives_fallback_message(self):
        from masova_agent.tools.backend_tools import submit_complaint
        with patch("masova_agent.tools.backend_tools.httpx.post") as mock_post:
            mock_post.side_effect = Exception("timeout")
            result = submit_complaint("CUST-1", "ORD-001", "The food was completely wrong order", _tool_context("CUST-1"))
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
            result = get_loyalty_points("CUST-1", _tool_context("CUST-1"))
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
            result = get_loyalty_points("CUST-1", _tool_context("CUST-1"))
        assert "PLATINUM" in result
        assert "highest" in result.lower()

    def test_api_error(self):
        from masova_agent.tools.backend_tools import get_loyalty_points
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
            mock_get.side_effect = Exception("timeout")
            result = get_loyalty_points("CUST-1", _tool_context("CUST-1"))
        assert "couldn't" in result.lower() or "error" in result.lower()

    def test_no_session_identity_declines_gracefully(self):
        from masova_agent.tools.backend_tools import get_loyalty_points
        result = get_loyalty_points("CUST-1", _tool_context(None))
        assert "log in" in result.lower() or "verify" in result.lower()


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
    def test_cancellable_order_submits_request_not_direct_cancel(self):
        from masova_agent.tools.backend_tools import cancel_order
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get, \
             patch("masova_agent.tools.backend_tools.httpx.post") as mock_post:
            mock_get.return_value = _mock_get(200, {"status": "RECEIVED"})
            mock_post.return_value = _mock_post(200, {
                "status": "RECEIVED",
                "cancellationRequested": True,
            })
            result = cancel_order("ORD-001", "Changed my mind", _tool_context("CUST-1"))
            called_path = mock_post.call_args.args[0]
        assert "/cancel-request" in called_path
        assert "/cancel" not in called_path.replace("/cancel-request", "")
        assert "manager" in result.lower() or "review" in result.lower()
        assert "cancelled" not in result.lower() or "not" in result.lower()

    def test_order_already_preparing_cannot_cancel(self):
        from masova_agent.tools.backend_tools import cancel_order
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_get(200, {"status": "PREPARING"})
            result = cancel_order("ORD-002", "Changed my mind", _tool_context("CUST-1"))
        assert "cannot be cancelled" in result.lower() or "already" in result.lower()

    def test_short_reason_rejected(self):
        from masova_agent.tools.backend_tools import cancel_order
        result = cancel_order("ORD-001", "no", _tool_context("CUST-1"))
        assert "reason" in result.lower()


# ---------------------------------------------------------------------------
# request_refund
# ---------------------------------------------------------------------------

class TestRequestRefund:
    def test_valid_refund_request_targets_pending_endpoint(self):
        from masova_agent.tools.backend_tools import request_refund
        with patch("masova_agent.tools.backend_tools.httpx.post") as mock_post:
            mock_post.return_value = _mock_post(201, {
                "refundId": "REF-123",
                "status": "PENDING_APPROVAL",
            })
            result = request_refund("ORD-001", "Wrong items delivered", _tool_context("CUST-1"))
            called_path = mock_post.call_args.args[0]
        assert "/refund/request" in called_path
        assert "pending" in result.lower() or "approval" in result.lower() or "manager" in result.lower()
        assert "REF-123" in result or "refund" in result.lower()

    def test_short_reason_rejected(self):
        from masova_agent.tools.backend_tools import request_refund
        result = request_refund("ORD-001", "bad", _tool_context("CUST-1"))
        assert "reason" in result.lower()

    def test_api_error_gives_fallback(self):
        from masova_agent.tools.backend_tools import request_refund
        with patch("masova_agent.tools.backend_tools.httpx.post") as mock_post:
            mock_post.side_effect = Exception("timeout")
            result = request_refund("ORD-001", "Completely wrong order received", _tool_context("CUST-1"))
        assert "3" in result or "days" in result.lower() or "logged" in result.lower()


# ---------------------------------------------------------------------------
# Session identity binding — chat-supplied customer_id must never override
# the verified session identity (Task 2: closes the gap where the LLM could
# extract an arbitrary customer_id from free chat text and pass it straight
# through to the backend call). The verified identity arrives via ADK's
# `ToolContext.state` (populated from `state_delta` at the FastAPI boundary,
# see `agent.py::send_message_async` / `main.py`), not via any
# LLM-controlled function argument.
# ---------------------------------------------------------------------------

class TestSessionIdentityBinding:
    def test_get_loyalty_points_ignores_llm_supplied_customer_id(self):
        from masova_agent.tools.backend_tools import get_loyalty_points
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_get(200, {"loyaltyPoints": 10, "loyaltyTier": "BRONZE"})
            get_loyalty_points("attacker-id", _tool_context("real-session-cust"))
            called_path = mock_get.call_args.args[0]
        assert "attacker-id" not in called_path
        assert "real-session-cust" in called_path

    def test_get_order_status_passes_session_customer_id_as_param(self):
        from masova_agent.tools.backend_tools import get_order_status
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_get(200, {"status": "RECEIVED", "orderNumber": "ORD-1"})
            get_order_status("ORD-1", _tool_context("real-session-cust"))
            params = mock_get.call_args.kwargs.get("params") or {}
        assert params.get("customerId") == "real-session-cust"

    def test_submit_complaint_ignores_llm_supplied_customer_id(self):
        from masova_agent.tools.backend_tools import submit_complaint
        with patch("masova_agent.tools.backend_tools.httpx.post") as mock_post:
            mock_post.return_value = _mock_post(201, {"id": "TKT-1"})
            submit_complaint("attacker-id", "ORD-001", "Food was cold and arrived late", _tool_context("real-session-cust"))
            body = mock_post.call_args.kwargs.get("json") or {}
        assert body.get("customerId") == "real-session-cust"
        assert body.get("customerId") != "attacker-id"

    def test_cancel_order_forwards_session_customer_id_in_headers(self):
        from masova_agent.tools.backend_tools import cancel_order
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get, \
             patch("masova_agent.tools.backend_tools.httpx.post") as mock_post:
            mock_get.return_value = _mock_get(200, {"status": "RECEIVED"})
            mock_post.return_value = _mock_post(200, {"cancellationRequested": True, "status": "RECEIVED"})
            cancel_order("ORD-001", "Changed my mind", _tool_context("real-session-cust"))
            headers = mock_post.call_args.kwargs.get("headers") or {}
        assert headers.get("X-User-Id") == "real-session-cust"
        assert headers.get("X-Customer-Id") == "real-session-cust"

    def test_request_refund_passes_session_customer_id_as_param(self):
        from masova_agent.tools.backend_tools import request_refund
        with patch("masova_agent.tools.backend_tools.httpx.post") as mock_post:
            mock_post.return_value = _mock_post(201, {"refundId": "REF-1"})
            request_refund("ORD-001", "Wrong items delivered", _tool_context("real-session-cust"))
            body = mock_post.call_args.kwargs.get("json") or {}
        assert body.get("customerId") == "real-session-cust"

    def test_no_session_identity_means_no_customer_id_leaks_through(self):
        """Anonymous session (no verified identity) — chat-supplied id must
        still never be trusted, even though there's nothing to substitute it
        with."""
        from masova_agent.tools.backend_tools import get_loyalty_points
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_get(200, {"loyaltyPoints": 0, "loyaltyTier": "BRONZE"})
            result = get_loyalty_points("attacker-id", _tool_context(None))
            called_path = mock_get.call_args.args[0] if mock_get.call_args else ""
        assert "attacker-id" not in called_path
        assert "couldn't" in result.lower() or "verify" in result.lower() or "log in" in result.lower()

    def test_unused_customer_id_arg_never_appears_in_logs(self, caplog):
        """Closes the gap flagged in review: the LLM-visible but unused/ignored
        `customer_id` argument on submit_complaint/get_loyalty_points (and the
        analogous session-bound argument handling in get_order_status,
        request_refund, cancel_order) must never reach logger.* output, even on
        the error path where _get/_post log status info. If a future edit wires
        this dead parameter into a log line, this test catches it."""
        from masova_agent.tools.backend_tools import (
            get_order_status,
            submit_complaint,
            get_loyalty_points,
            request_refund,
            cancel_order,
        )

        attacker_id = "attacker-style-id-9999"
        session_id = "real-session-cust"

        with caplog.at_level("DEBUG"):
            with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
                mock_get.side_effect = Exception("boom")
                get_order_status("ORD-1", _tool_context(session_id))
                get_loyalty_points(attacker_id, _tool_context(session_id))

            with patch("masova_agent.tools.backend_tools.httpx.post") as mock_post:
                mock_post.side_effect = Exception("boom")
                submit_complaint(attacker_id, "ORD-1", "Food was cold and arrived late", _tool_context(session_id))
                request_refund("ORD-1", "Wrong items delivered", _tool_context(session_id))

            with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get, \
                 patch("masova_agent.tools.backend_tools.httpx.post") as mock_post:
                mock_get.return_value = _mock_get(200, {"status": "RECEIVED"})
                mock_post.side_effect = Exception("boom")
                cancel_order("ORD-1", "Changed my mind", _tool_context(session_id))

        for record in caplog.records:
            assert attacker_id not in record.getMessage()


# ---------------------------------------------------------------------------
# Task 3: X-User-Type header — now sends AGENT instead of hardcoded MANAGER
# ---------------------------------------------------------------------------

class TestUserTypeHeader:
    """Verify outbound calls no longer claim MANAGER privilege unconditionally."""

    def test_get_order_status_sends_agent_header(self):
        """Outbound call to fetch order status must include X-User-Type: AGENT."""
        from masova_agent.tools.backend_tools import get_order_status
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_get(200, {
                "status": "RECEIVED",
                "orderNumber": "ORD-1",
                "items": [],
            })
            get_order_status("ORD-1", _tool_context("CUST-1"))
            headers = mock_get.call_args.kwargs.get("headers", {})
        assert headers.get("X-User-Type") == "AGENT", \
            f"Expected X-User-Type: AGENT, got {headers.get('X-User-Type')}"

    def test_get_menu_items_sends_agent_header(self):
        """Menu fetch must not claim MANAGER privilege."""
        from masova_agent.tools.backend_tools import get_menu_items
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_get(200, {"content": []})
            get_menu_items("store-1")
            headers = mock_get.call_args.kwargs.get("headers", {})
        assert headers.get("X-User-Type") == "AGENT"

    def test_get_store_hours_sends_agent_header(self):
        """Store hours fetch must not claim MANAGER privilege."""
        from masova_agent.tools.backend_tools import get_store_hours
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_get(200, {
                "name": "Store",
                "status": "ACTIVE",
            })
            get_store_hours("store-1")
            headers = mock_get.call_args.kwargs.get("headers", {})
        assert headers.get("X-User-Type") == "AGENT"

    def test_submit_complaint_records_pending_not_immediate_action(self):
        from masova_agent.tools.backend_tools import submit_complaint
        with patch("masova_agent.tools.backend_tools.httpx.post") as mock_post:
            mock_post.return_value = _mock_post(201, {"id": "TKT-1", "status": "PENDING"})
            result = submit_complaint("CUST-1", "ORD-001", "Food was cold and arrived late", _tool_context("CUST-1"))
            called_path = mock_post.call_args.args[0]
        assert "/reviews/complaints" in called_path
        assert "manager" in result.lower() or "review" in result.lower()

    def test_submit_complaint_sends_agent_header(self):
        """Complaint submission must not claim MANAGER privilege."""
        from masova_agent.tools.backend_tools import submit_complaint
        with patch("masova_agent.tools.backend_tools.httpx.post") as mock_post:
            mock_post.return_value = _mock_post(201, {"id": "TKT-1"})
            submit_complaint("CUST-1", "ORD-001", "Food was cold and arrived late", _tool_context("CUST-1"))
            headers = mock_post.call_args.kwargs.get("headers", {})
        assert headers.get("X-User-Type") == "AGENT"

    def test_get_loyalty_points_sends_agent_header(self):
        """Loyalty points fetch must not claim MANAGER privilege."""
        from masova_agent.tools.backend_tools import get_loyalty_points
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_get(200, {
                "loyaltyPoints": 100,
                "loyaltyTier": "BRONZE",
            })
            get_loyalty_points("CUST-1", _tool_context("CUST-1"))
            headers = mock_get.call_args.kwargs.get("headers", {})
        assert headers.get("X-User-Type") == "AGENT"

    def test_get_store_wait_time_sends_agent_header(self):
        """Wait time fetch must not claim MANAGER privilege."""
        from masova_agent.tools.backend_tools import get_store_wait_time
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_get(200, {"totalElements": 0})
            get_store_wait_time("store-1")
            headers = mock_get.call_args.kwargs.get("headers", {})
        assert headers.get("X-User-Type") == "AGENT"

    def test_cancel_order_sends_agent_header(self):
        """Cancellation request must not claim MANAGER privilege."""
        from masova_agent.tools.backend_tools import cancel_order
        with patch("masova_agent.tools.backend_tools.httpx.get") as mock_get, \
             patch("masova_agent.tools.backend_tools.httpx.post") as mock_post:
            mock_get.return_value = _mock_get(200, {"status": "RECEIVED"})
            mock_post.return_value = _mock_post(200, {"cancellationRequested": True, "status": "RECEIVED"})
            cancel_order("ORD-001", "Changed my mind", _tool_context("CUST-1"))
            headers = mock_post.call_args.kwargs.get("headers", {})
        assert headers.get("X-User-Type") == "AGENT"

    def test_request_refund_sends_agent_header(self):
        """Refund request must not claim MANAGER privilege."""
        from masova_agent.tools.backend_tools import request_refund
        with patch("masova_agent.tools.backend_tools.httpx.post") as mock_post:
            mock_post.return_value = _mock_post(201, {"refundId": "REF-1"})
            request_refund("ORD-001", "Wrong items delivered", _tool_context("CUST-1"))
            headers = mock_post.call_args.kwargs.get("headers", {})
        assert headers.get("X-User-Type") == "AGENT"

    def test_outbound_calls_never_include_manager_header(self):
        """Comprehensive check: no outbound call should ever include X-User-Type: MANAGER."""
        from masova_agent.tools.backend_tools import (
            get_order_status,
            get_menu_items,
            get_store_hours,
            submit_complaint,
            get_loyalty_points,
            get_store_wait_time,
            cancel_order,
            request_refund,
        )

        functions_to_test = [
            (get_order_status, ("ORD-1", _tool_context("CUST-1")), "httpx.get"),
            (get_menu_items, ("store-1",), "httpx.get"),
            (get_store_hours, ("store-1",), "httpx.get"),
            (submit_complaint, ("CUST-1", "ORD-1", "Food was cold", _tool_context("CUST-1")), "httpx.post"),
            (get_loyalty_points, ("CUST-1", _tool_context("CUST-1")), "httpx.get"),
            (get_store_wait_time, ("store-1",), "httpx.get"),
            (cancel_order, ("ORD-1", "reason", _tool_context("CUST-1")), "httpx.post"),
            (request_refund, ("ORD-1", "reason", _tool_context("CUST-1")), "httpx.post"),
        ]

        for func, args, mock_target in functions_to_test:
            with patch(f"masova_agent.tools.backend_tools.{mock_target}") as mock_http:
                if "get" in mock_target:
                    mock_http.return_value = _mock_get(200, {"status": "RECEIVED", "content": []})
                else:
                    mock_http.return_value = _mock_post(200, {"id": "test"})

                try:
                    func(*args)
                except Exception:
                    pass  # We're only interested in the headers call

                if mock_http.called:
                    headers = mock_http.call_args.kwargs.get("headers", {})
                    user_type = headers.get("X-User-Type")
                    assert user_type != "MANAGER", \
                        f"{func.__name__} incorrectly sent X-User-Type: MANAGER"
                    assert user_type == "AGENT", \
                        f"{func.__name__} should send X-User-Type: AGENT, got {user_type}"
