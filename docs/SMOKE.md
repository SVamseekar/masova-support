# Live smoke

Optional. Non-fatal if the platform backend is offline. Never commit tokens.

| Variable | Purpose | Default |
|----------|---------|---------|
| `BACKEND_URL` | Platform gateway | `http://localhost:8080` |
| `SUPPORT_URL` | This service | `http://127.0.0.1:8000` |
| `AGENT_TOKEN` | Ops → backend | — |
| `AGENT_TRIGGER_API_KEY` | Triggers + proposals | — |
| `JWT` | Customer HS512 JWT for chat | — |

```bash
uvicorn src.masova_agent.main:app --host 0.0.0.0 --port 8000
./scripts/smoke_backend.sh          # set SMOKE_STRICT=1 to fail hard
```

| # | Step | Expect |
|---|------|--------|
| 1 | `GET $SUPPORT_URL/health` | 200 |
| 2 | `GET $BACKEND_URL/actuator/health` or `/health` | 200 or skip if offline |
| 3 | `POST /agent/chat` without JWT | 401 |
| 4 | `POST /agent/chat` with `Authorization: Bearer $JWT` | 200 + reply or safe fallback |
| 5 | Trigger without `X-Agent-Api-Key` | 401 (or 503 if key unset) |
| 6 | `POST /agents/inventory-reorder/trigger` with key | 200 JSON |
| 7 | `POST /agents/dynamic-pricing/trigger` with key | 200; no live price PATCH |
| 8 | `GET /agent/proposals?storeId=...` with key | 200 list |
| 9 | Logs | no tokens/JWT |
| 10 | Proposals | draft + manager notify only |

```bash
curl -sf "$SUPPORT_URL/health"
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$SUPPORT_URL/agent/chat" \
  -H 'Content-Type: application/json' -d '{"message":"hi"}'
curl -s -X POST "$SUPPORT_URL/agent/chat" \
  -H "Authorization: Bearer $JWT" -H 'Content-Type: application/json' \
  -d '{"message":"What is my loyalty balance?"}'
curl -s -X POST "$SUPPORT_URL/agents/inventory-reorder/trigger" \
  -H "X-Agent-Api-Key: $AGENT_TRIGGER_API_KEY"
curl -s "$SUPPORT_URL/agent/proposals?status=PENDING" \
  -H "X-Agent-Api-Key: $AGENT_TRIGGER_API_KEY"
```

CI does not run this script. See [RUNBOOK.md](RUNBOOK.md) for outages.
