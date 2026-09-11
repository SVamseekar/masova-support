# Live smoke (optional)

Non-fatal if the platform backend is offline. Set `BACKEND_URL` to the lab or staging gateway.

## Env

```bash
export BACKEND_URL="${BACKEND_URL:-http://localhost:8080}"
export AGENT_TOKEN="..."           # ops → platform
export AGENT_TRIGGER_API_KEY="..." # manual triggers
export JWT="..."                   # customer JWT for chat (HS512)
export SUPPORT_URL="${SUPPORT_URL:-http://127.0.0.1:8000}"
```

Never commit real tokens. Prefer gitignored `.env`.

## Script

```bash
./scripts/smoke_backend.sh
```

Or manual:

```bash
# Platform health (path may vary by gateway)
curl -sf "$BACKEND_URL/actuator/health" || curl -sf "$BACKEND_URL/health" || true

# Support health
curl -sf "$SUPPORT_URL/health"

# Chat without JWT → 401
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$SUPPORT_URL/agent/chat" \
  -H 'Content-Type: application/json' \
  -d '{"message":"hi"}'

# Chat with JWT (if available)
curl -s -X POST "$SUPPORT_URL/agent/chat" \
  -H "Authorization: Bearer $JWT" \
  -H 'Content-Type: application/json' \
  -d '{"message":"What is my loyalty balance?"}'

# Ops triggers (trigger key)
curl -s -X POST "$SUPPORT_URL/agents/inventory-reorder/trigger" \
  -H "X-API-Key: $AGENT_TRIGGER_API_KEY"
curl -s -X POST "$SUPPORT_URL/agents/dynamic-pricing/trigger" \
  -H "X-API-Key: $AGENT_TRIGGER_API_KEY"
```

## Pass criteria

| Check | Expect |
|-------|--------|
| Support `/health` | 200 |
| Chat no JWT | 401 |
| Chat with JWT | 200 + reply (or graceful fallback) |
| Trigger without key | 401/403 |
| Trigger with key | 200 + JSON body; `_runtime` present when wired |
| Offline backend | Script exits 0 with “skipped” notes — CI must not depend on this |

See also `docs/SMOKE_CHECKLIST.md` (Phase F full checklist).
