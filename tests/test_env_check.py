import pytest
from masova_agent.utils.env_check import check_environment, required_vars


def test_required_vars_includes_jwt_secret_and_agent_keys():
    names = required_vars()
    assert "JWT_SECRET" in names
    assert "AGENT_TRIGGER_API_KEY" in names or "AGENT_API_KEYS" in names


def test_check_environment_passes_when_all_set(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("AGENT_TRIGGER_API_KEY", "test-key")
    monkeypatch.setenv("BACKEND_URL", "http://localhost:8080")
    missing = check_environment(strict=False)
    assert missing == []


def test_check_environment_reports_missing_jwt_secret(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("AGENT_TRIGGER_API_KEY", "test-key")
    monkeypatch.setenv("BACKEND_URL", "http://localhost:8080")
    missing = check_environment(strict=False)
    assert "JWT_SECRET" in missing


def test_check_environment_accepts_agent_api_keys_instead_of_trigger_key(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.delenv("AGENT_TRIGGER_API_KEY", raising=False)
    monkeypatch.setenv("AGENT_API_KEYS", '[{"key": "k1", "scopes": ["*"]}]')
    monkeypatch.setenv("BACKEND_URL", "http://localhost:8080")
    missing = check_environment(strict=False)
    assert missing == []


def test_check_environment_strict_raises_with_all_missing_names(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("AGENT_TRIGGER_API_KEY", raising=False)
    monkeypatch.delenv("AGENT_API_KEYS", raising=False)
    monkeypatch.setenv("BACKEND_URL", "http://localhost:8080")
    with pytest.raises(EnvironmentError) as exc_info:
        check_environment(strict=True)
    assert "JWT_SECRET" in str(exc_info.value)
