"""Contract fixture sanity + tool parsing against fixture shapes."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from unittest.mock import patch

from masova_agent.auth import AgentIdentity, bind_identity, reset_identity
from tests.fixtures.backend_contracts import (
    CANCELLABLE_STATUSES,
    ORDER_STATUSES,
    SAMPLE_CANCEL_REQUEST_RESPONSE,
    SAMPLE_CUSTOMER,
    SAMPLE_MENU_PAGE,
    SAMPLE_ORDER,
    SAMPLE_REFUND_RESPONSE,
    SAMPLE_STORE_FLAT,
    SAMPLE_STORE_NESTED,
)


@pytest.fixture(autouse=True)
def _id():
    t = bind_identity(AgentIdentity("CUST-1", "CUSTOMER", None, "jwt"))
    yield
    reset_identity(t)


def _ok(body):
    from tests.test_backend_tools import _mock_get, _mock_post
    return _mock_get(200, body) if True else None


class TestContractFixtures:
    def test_order_statuses_cover_cancellable(self):
        assert CANCELLABLE_STATUSES <= ORDER_STATUSES

    def test_get_order_status_fixture(self):
        from masova_agent.tools.backend_tools import get_order_status
        from tests.test_backend_tools import _mock_get
        with patch("masova_agent.tools.backend_tools.httpx.get") as g:
            g.return_value = _mock_get(200, SAMPLE_ORDER)
            text = get_order_status("ord-abc")
        assert "PREPARING" not in text or "kitchen" in text.lower() or "prepared" in text.lower()
        assert "Margherita" in text

    def test_menu_fixture(self):
        from masova_agent.tools.backend_tools import get_menu_items
        from tests.test_backend_tools import _mock_get
        with patch("masova_agent.tools.backend_tools.httpx.get") as g:
            g.return_value = _mock_get(200, SAMPLE_MENU_PAGE)
            text = get_menu_items("DOM001")
        assert "Margherita" in text

    def test_store_shapes(self):
        from masova_agent.tools.backend_tools import get_store_hours
        from tests.test_backend_tools import _mock_get
        with patch("masova_agent.tools.backend_tools.httpx.get") as g:
            g.return_value = _mock_get(200, SAMPLE_STORE_NESTED)
            assert "ACTIVE" in get_store_hours("DOM001")
            g.return_value = _mock_get(200, SAMPLE_STORE_FLAT)
            assert "OPEN" in get_store_hours("store-1")

    def test_customer_loyalty_fixture(self):
        from masova_agent.tools.backend_tools import get_loyalty_points
        from tests.test_backend_tools import _mock_get
        with patch("masova_agent.tools.backend_tools.httpx.get") as g:
            g.return_value = _mock_get(200, SAMPLE_CUSTOMER)
            text = get_loyalty_points()
        assert "3200" in text and "GOLD" in text

    def test_refund_pending_fixture(self):
        from masova_agent.tools.backend_tools import request_refund
        from tests.test_backend_tools import _mock_post
        with patch("masova_agent.tools.backend_tools.httpx.post") as p:
            p.return_value = _mock_post(201, SAMPLE_REFUND_RESPONSE)
            text = request_refund("ord-abc", "Wrong items delivered")
        assert "pending manager approval" in text.lower()

    def test_cancel_pending_fixture(self):
        from masova_agent.tools.backend_tools import cancel_order
        from tests.test_backend_tools import _mock_get, _mock_post
        with patch("masova_agent.tools.backend_tools.httpx.get") as g, \
             patch("masova_agent.tools.backend_tools.httpx.post") as p:
            g.return_value = _mock_get(200, {"status": "RECEIVED"})
            p.return_value = _mock_post(200, SAMPLE_CANCEL_REQUEST_RESPONSE)
            text = cancel_order("ord-abc", "Changed my mind")
        assert "manager" in text.lower()
