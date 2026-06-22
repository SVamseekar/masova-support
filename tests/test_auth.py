"""
Unit tests for src/masova_agent/auth.py — API-key auth dependencies.

These test the dependency functions directly (no live FastAPI app needed),
mirroring the existing pattern of mocking config via get_config().
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException


def _mock_config(agent_api_key="test-agent-key", internal_trigger_secret="test-trigger-secret"):
    cfg = MagicMock()
    cfg.agent_api_key = agent_api_key
    cfg.internal_trigger_secret = internal_trigger_secret
    return cfg


# ---------------------------------------------------------------------------
# require_caller_identity (used on /agent/chat)
# ---------------------------------------------------------------------------

class TestRequireCallerIdentity:
    def test_missing_credential_raises_401(self):
        from masova_agent.auth import require_caller_identity

        with patch("masova_agent.auth.get_config", return_value=_mock_config()):
            with pytest.raises(HTTPException) as exc_info:
                require_caller_identity(authorization=None, x_api_key=None, x_customer_id=None)

        assert exc_info.value.status_code == 401

    def test_wrong_api_key_raises_401(self):
        from masova_agent.auth import require_caller_identity

        with patch("masova_agent.auth.get_config", return_value=_mock_config()):
            with pytest.raises(HTTPException) as exc_info:
                require_caller_identity(
                    authorization="Bearer wrong-key", x_api_key=None, x_customer_id=None
                )

        assert exc_info.value.status_code == 401

    def test_no_agent_api_key_configured_raises_401(self):
        """If AGENT_API_KEY isn't configured server-side, fail closed, not open."""
        from masova_agent.auth import require_caller_identity

        with patch("masova_agent.auth.get_config", return_value=_mock_config(agent_api_key="")):
            with pytest.raises(HTTPException) as exc_info:
                require_caller_identity(
                    authorization="Bearer anything", x_api_key=None, x_customer_id=None
                )

        assert exc_info.value.status_code == 401

    def test_valid_bearer_token_with_customer_id_header_returns_identity(self):
        from masova_agent.auth import require_caller_identity

        with patch("masova_agent.auth.get_config", return_value=_mock_config()):
            identity = require_caller_identity(
                authorization="Bearer test-agent-key",
                x_api_key=None,
                x_customer_id="cust-123",
            )

        assert identity.customer_id == "cust-123"

    def test_valid_x_api_key_header_accepted(self):
        from masova_agent.auth import require_caller_identity

        with patch("masova_agent.auth.get_config", return_value=_mock_config()):
            identity = require_caller_identity(
                authorization=None,
                x_api_key="test-agent-key",
                x_customer_id="cust-456",
            )

        assert identity.customer_id == "cust-456"

    def test_valid_credential_without_customer_id_header_is_anonymous(self):
        """Anonymous callers (no X-Customer-Id) are allowed — they just can't claim a customerId."""
        from masova_agent.auth import require_caller_identity

        with patch("masova_agent.auth.get_config", return_value=_mock_config()):
            identity = require_caller_identity(
                authorization="Bearer test-agent-key", x_api_key=None, x_customer_id=None
            )

        assert identity.customer_id is None


# ---------------------------------------------------------------------------
# enforce_customer_id_match (used to reject body customerId mismatches)
# ---------------------------------------------------------------------------

class TestEnforceCustomerIdMatch:
    def test_body_customer_id_matches_identity_passes(self):
        from masova_agent.auth import enforce_customer_id_match, CallerIdentity

        identity = CallerIdentity(customer_id="cust-123")
        # Should not raise
        enforce_customer_id_match(identity, body_customer_id="cust-123")

    def test_body_customer_id_mismatch_raises_403(self):
        from masova_agent.auth import enforce_customer_id_match, CallerIdentity

        identity = CallerIdentity(customer_id="cust-123")
        with pytest.raises(HTTPException) as exc_info:
            enforce_customer_id_match(identity, body_customer_id="cust-999")

        assert exc_info.value.status_code == 403

    def test_body_customer_id_with_anonymous_identity_raises_403(self):
        """Caller has no verified customerId but claims one in body → reject."""
        from masova_agent.auth import enforce_customer_id_match, CallerIdentity

        identity = CallerIdentity(customer_id=None)
        with pytest.raises(HTTPException) as exc_info:
            enforce_customer_id_match(identity, body_customer_id="cust-123")

        assert exc_info.value.status_code == 403

    def test_no_body_customer_id_with_anonymous_identity_passes(self):
        from masova_agent.auth import enforce_customer_id_match, CallerIdentity

        identity = CallerIdentity(customer_id=None)
        # Should not raise — anonymous chat with no claimed customerId is fine
        enforce_customer_id_match(identity, body_customer_id=None)

    def test_no_body_customer_id_with_verified_identity_passes(self):
        from masova_agent.auth import enforce_customer_id_match, CallerIdentity

        identity = CallerIdentity(customer_id="cust-123")
        # Should not raise — caller didn't claim anything in the body
        enforce_customer_id_match(identity, body_customer_id=None)


# ---------------------------------------------------------------------------
# require_internal_trigger_auth (used on /agents/{name}/trigger)
# ---------------------------------------------------------------------------

class TestRequireInternalTriggerAuth:
    def test_missing_credential_raises_401(self):
        from masova_agent.auth import require_internal_trigger_auth

        with patch("masova_agent.auth.get_config", return_value=_mock_config()):
            with pytest.raises(HTTPException) as exc_info:
                require_internal_trigger_auth(authorization=None, x_api_key=None)

        assert exc_info.value.status_code == 401

    def test_wrong_secret_raises_401(self):
        from masova_agent.auth import require_internal_trigger_auth

        with patch("masova_agent.auth.get_config", return_value=_mock_config()):
            with pytest.raises(HTTPException) as exc_info:
                require_internal_trigger_auth(authorization="Bearer wrong-secret", x_api_key=None)

        assert exc_info.value.status_code == 401

    def test_no_secret_configured_raises_401(self):
        """If INTERNAL_TRIGGER_SECRET isn't configured server-side, fail closed."""
        from masova_agent.auth import require_internal_trigger_auth

        with patch(
            "masova_agent.auth.get_config",
            return_value=_mock_config(internal_trigger_secret=""),
        ):
            with pytest.raises(HTTPException) as exc_info:
                require_internal_trigger_auth(authorization="Bearer anything", x_api_key=None)

        assert exc_info.value.status_code == 401

    def test_valid_bearer_secret_passes(self):
        from masova_agent.auth import require_internal_trigger_auth

        with patch("masova_agent.auth.get_config", return_value=_mock_config()):
            # Should not raise
            require_internal_trigger_auth(authorization="Bearer test-trigger-secret", x_api_key=None)

    def test_valid_x_api_key_secret_passes(self):
        from masova_agent.auth import require_internal_trigger_auth

        with patch("masova_agent.auth.get_config", return_value=_mock_config()):
            require_internal_trigger_auth(authorization=None, x_api_key="test-trigger-secret")
