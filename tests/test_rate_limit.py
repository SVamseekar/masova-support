"""Multi-tier sliding-window rate limiter."""

import time

from fastapi.testclient import TestClient

from masova_agent.runtime.rate_limit import (
    _reset_for_tests,
    check_rate_limit,
    classify_route_tier,
)


def setup_function():
    _reset_for_tests()


def test_classify_ai_tier():
    assert classify_route_tier("/agent/chat", "POST") == "TIER_AI"
    assert classify_route_tier("/agents/demand-forecast/trigger", "POST") == "TIER_AI"


def test_classify_read_tier():
    assert classify_route_tier("/agent/proposals", "GET") == "TIER_READ"
    assert classify_route_tier("/agent/runs", "GET") == "TIER_READ"


def test_classify_exempt_health():
    assert classify_route_tier("/health", "GET") == "TIER_EXEMPT"


def test_bucket_allows_up_to_budget_then_blocks():
    for _ in range(5):
        assert check_rate_limit("key1", "TIER_DEFAULT", budget=5, window_seconds=60) is True
    assert check_rate_limit("key1", "TIER_DEFAULT", budget=5, window_seconds=60) is False


def test_bucket_refills_after_window():
    for _ in range(2):
        check_rate_limit("key2", "TIER_DEFAULT", budget=2, window_seconds=0.2)
    assert check_rate_limit("key2", "TIER_DEFAULT", budget=2, window_seconds=0.2) is False
    time.sleep(0.25)
    assert check_rate_limit("key2", "TIER_DEFAULT", budget=2, window_seconds=0.2) is True


def test_separate_keys_independent_buckets():
    for _ in range(3):
        check_rate_limit("keyA", "TIER_DEFAULT", budget=3, window_seconds=60)
    assert check_rate_limit("keyB", "TIER_DEFAULT", budget=3, window_seconds=60) is True


def test_health_never_rate_limited():
    from masova_agent.main import app

    client = TestClient(app, raise_server_exceptions=False)
    for _ in range(500):
        resp = client.get("/health")
        assert resp.status_code == 200
