"""
Integration tests for FastAPI endpoints in src/masova_agent/main.py —
auth gating on /agent/chat and /agents/{name}/trigger.

Uses FastAPI's TestClient against the real app, with config patched via
env vars (loaded into masova_agent.utils.config.Config) and the agent's
backend calls mocked so no live Gemini/Redis/RabbitMQ connection is needed.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


AGENT_API_KEY = "test-agent-api-key"
INTERNAL_TRIGGER_SECRET = "test-internal-trigger-secret"


@pytest.fixture
def client():
    """Build a TestClient with auth secrets configured via the global config."""
    os.environ["AGENT_API_KEY"] = AGENT_API_KEY
    os.environ["INTERNAL_TRIGGER_SECRET"] = INTERNAL_TRIGGER_SECRET
    os.environ.setdefault("GOOGLE_API_KEY", "test-google-key")

    from masova_agent.utils.config import reload_config
    reload_config()

    from contextlib import asynccontextmanager

    from fastapi.testclient import TestClient
    from masova_agent import main as main_module

    # Bypass the app's real lifespan (starts a global APScheduler singleton
    # and a RabbitMQ consumer) — irrelevant to auth behaviour, and unsafe to
    # start repeatedly across tests since the scheduler is a module-level
    # global that errors on a second .start() call.
    @asynccontextmanager
    async def _noop_lifespan(_app):
        yield

    original_lifespan = main_module.app.router.lifespan_context
    main_module.app.router.lifespan_context = _noop_lifespan
    try:
        with TestClient(main_module.app) as c:
            yield c
    finally:
        main_module.app.router.lifespan_context = original_lifespan


# ---------------------------------------------------------------------------
# /agent/chat
# ---------------------------------------------------------------------------

class TestChatAuth:
    def test_no_credential_returns_401(self, client):
        resp = client.post("/agent/chat", json={"message": "hi"})
        assert resp.status_code == 401

    def test_invalid_credential_returns_401(self, client):
        resp = client.post(
            "/agent/chat",
            json={"message": "hi"},
            headers={"Authorization": "Bearer wrong-key"},
        )
        assert resp.status_code == 401

    def test_valid_credential_with_mismatched_customer_id_returns_403(self, client):
        resp = client.post(
            "/agent/chat",
            json={"message": "hi", "customerId": "cust-999"},
            headers={
                "Authorization": f"Bearer {AGENT_API_KEY}",
                "X-Customer-Id": "cust-123",
            },
        )
        assert resp.status_code == 403

    def test_valid_credential_claiming_customer_id_without_verified_identity_returns_403(self, client):
        """Caller has valid API key but no X-Customer-Id header, yet claims one in body."""
        resp = client.post(
            "/agent/chat",
            json={"message": "hi", "customerId": "cust-123"},
            headers={"Authorization": f"Bearer {AGENT_API_KEY}"},
        )
        assert resp.status_code == 403

    def test_valid_credential_matching_customer_id_returns_200(self, client):
        with patch(
            "masova_agent.main.send_message_async",
            new=AsyncMock(return_value=("Hello there!", "session-abc")),
        ), patch.object(
            __import__("masova_agent.main", fromlist=["_session_service"])._session_service,
            "append_turn",
            new=AsyncMock(),
        ):
            resp = client.post(
                "/agent/chat",
                json={"message": "hi", "customerId": "cust-123"},
                headers={
                    "Authorization": f"Bearer {AGENT_API_KEY}",
                    "X-Customer-Id": "cust-123",
                },
            )

        assert resp.status_code == 200
        assert resp.json()["reply"] == "Hello there!"

    def test_valid_credential_anonymous_no_customer_id_returns_200(self, client):
        with patch(
            "masova_agent.main.send_message_async",
            new=AsyncMock(return_value=("Hello there!", "session-xyz")),
        ), patch.object(
            __import__("masova_agent.main", fromlist=["_session_service"])._session_service,
            "append_turn",
            new=AsyncMock(),
        ):
            resp = client.post(
                "/agent/chat",
                json={"message": "hi"},
                headers={"X-API-Key": AGENT_API_KEY},
            )

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# /agents/{name}/trigger
# ---------------------------------------------------------------------------

class TestTriggerAuth:
    def test_trigger_without_auth_returns_401(self, client):
        resp = client.post("/agents/demand-forecast/trigger")
        assert resp.status_code == 401

    def test_trigger_with_wrong_secret_returns_401(self, client):
        resp = client.post(
            "/agents/inventory-reorder/trigger",
            headers={"Authorization": "Bearer wrong-secret"},
        )
        assert resp.status_code == 401

    def test_trigger_with_valid_secret_returns_200(self, client):
        with patch(
            "masova_agent.agents.demand_forecasting_agent.run_demand_forecast",
            new=AsyncMock(return_value={"status": "ok"}),
        ):
            resp = client.post(
                "/agents/demand-forecast/trigger",
                headers={"Authorization": f"Bearer {INTERNAL_TRIGGER_SECRET}"},
            )

        assert resp.status_code == 200

    def test_all_trigger_endpoints_require_auth(self, client):
        """Every /agents/*/trigger route must reject unauthenticated calls."""
        trigger_paths = [
            "/agents/demand-forecast/trigger",
            "/agents/inventory-reorder/trigger",
            "/agents/churn-prevention/trigger",
            "/agents/shift-optimisation/trigger",
            "/agents/kitchen-coach/trigger",
            "/agents/dynamic-pricing/trigger",
        ]
        for path in trigger_paths:
            resp = client.post(path)
            assert resp.status_code == 401, f"{path} did not require auth"

        # review-response/trigger requires a body too, but auth must run first
        resp = client.post("/agents/review-response/trigger", json={})
        assert resp.status_code == 401
