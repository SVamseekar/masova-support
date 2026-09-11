"""
Operator tool: reports whether the configured MaSoVa backend is actually
reachable — DNS, TCP, and an unauthenticated HTTP health check. Not imported
by the running app; run manually: `python scripts/check_backend_connectivity.py`

Health path is GET /health on the Java api-gateway
(ApiGatewayApplication @GetMapping("/health")), not Spring Actuator.
A non-200 still means TCP+HTTP reached the process; only a connection
failure means the gateway is not listening.
"""

from __future__ import annotations

import os
import socket
import sys
from urllib.parse import urlparse

import httpx

# Confirmed against MaSoVa-restaurant-management-system/api-gateway
# ApiGatewayApplication.java — not /actuator/health.
HEALTH_PATH = "/health"


def check_dns(host: str) -> bool:
    try:
        socket.gethostbyname(host)
        return True
    except socket.error:
        return False


def check_tcp(host: str, port: int, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def check_http_health(url: str, timeout: float = 4.0) -> tuple[bool, int | None]:
    try:
        resp = httpx.get(url, timeout=timeout)
        return True, resp.status_code
    except Exception:
        return False, None


def main() -> int:
    backend_url = os.getenv("BACKEND_URL", "http://localhost:8080")
    parsed = urlparse(backend_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    print(f"Checking backend connectivity: {backend_url}")

    dns_ok = check_dns(host)
    print(f"  DNS resolve {host}: {'OK' if dns_ok else 'FAILED'}")

    tcp_ok = check_tcp(host, port)
    print(f"  TCP connect {host}:{port}: {'OK' if tcp_ok else 'FAILED'}")

    if tcp_ok:
        health_url = f"{backend_url.rstrip('/')}{HEALTH_PATH}"
        reachable, status = check_http_health(health_url)
        if reachable:
            print(f"  HTTP GET {health_url}: OK ({status})")
            if status != 200:
                print(
                    "  Note: gateway answered but status is not 200. "
                    "TCP+HTTP layers work; the health path or auth may differ."
                )
        else:
            print(f"  HTTP GET {health_url}: FAILED")
        # Any HTTP response proves the gateway process is up.
        all_ok = dns_ok and tcp_ok and reachable
    else:
        print("  Skipping HTTP check — TCP connection failed.")
        all_ok = False

    print("RESULT:", "REACHABLE" if all_ok else "NOT REACHABLE")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
