import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.check_backend_connectivity import (  # noqa: E402
    check_dns,
    check_http_health,
    check_tcp,
)


def test_check_dns_resolves_localhost():
    assert check_dns("localhost") is True


def test_check_dns_fails_for_garbage_host():
    assert check_dns("this-host-does-not-exist.invalid") is False


def test_check_tcp_reports_closed_port():
    # Port 1 is reserved/unlikely to be open on localhost in test environments.
    assert check_tcp("127.0.0.1", 1, timeout=0.5) is False


def test_check_http_health_reports_status_code():
    with patch("scripts.check_backend_connectivity.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200)
        reachable, status = check_http_health("http://example.invalid/health")
    assert reachable is True
    assert status == 200


def test_check_http_health_handles_connection_error():
    with patch("scripts.check_backend_connectivity.httpx.get") as mock_get:
        mock_get.side_effect = Exception("connection refused")
        reachable, status = check_http_health("http://example.invalid/health")
    assert reachable is False
    assert status is None
