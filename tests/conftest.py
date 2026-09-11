"""
Pytest configuration for masova-support tests.
"""

import os
import sys
from pathlib import Path

# Fixture values only (never real secrets). setdefault so CI/job env wins.
# Needed because main.py runs check_environment() at import time; tests that
# import the app cannot rely on per-test monkeypatch if collection/import
# happens first. Matches CI's JWT_SECRET / AGENT_TRIGGER_API_KEY / BACKEND_URL.
os.environ.setdefault(
    "JWT_SECRET",
    "test-secret-at-least-64-characters-long-for-hs512-aaaaaaaaaaaaaaaaaaaaaa",
)
os.environ.setdefault("AGENT_TRIGGER_API_KEY", "test-trigger-key")
os.environ.setdefault("BACKEND_URL", "http://127.0.0.1:9")

_src = str(Path(__file__).parent.parent / "src")
# Insert at position 0 AND remove any path entry pointing at the legacy
# top-level masova_agent/ package so src/masova_agent/ always wins.
_root = str(Path(__file__).parent.parent)
if _root in sys.path:
    sys.path.remove(_root)
if _src not in sys.path:
    sys.path.insert(0, _src)

collect_ignore = ["test_scenarios.py"]
