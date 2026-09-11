# Live backend integration tests

Excluded from `pytest tests/` (see `addopts = ["-m", "not integration"]` in `pyproject.toml`).

These tests call the real MaSoVa Java api-gateway via `ops_tools` (the #52–#55 path fixes). CI must never run them: it has no LAN access to the Dell.

## Run

```bash
RUN_INTEGRATION_TESTS=1 \
  BACKEND_URL=http://192.168.50.88:8080 \
  AGENT_TOKEN=<ops bearer token> \
  TEST_STORE_ID=DOM001 \
  pytest -m integration
```

Optional:

- `TEST_LIVE_WRITES=1` — also POST a DRAFT purchase order (`create_draft_po`). Off by default so a read-only check cannot create Java-side rows.
- `TEST_SUPPLIER_ID` — used only with `TEST_LIVE_WRITES=1`.

Without `RUN_INTEGRATION_TESTS=1`, collected tests skip (no network calls).

Confirm the gateway is up first:

```bash
BACKEND_URL=http://192.168.50.88:8080 python scripts/check_backend_connectivity.py
```
