# Agent Platform (v1)

Shared runtime for all MaSoVa support operators: support chat plus seven scheduled/event ops agents.

## Architecture

```text
Chat JWT / Trigger API key / APScheduler / RabbitMQ
        → FastAPI
        → AgentRuntime (policy, optional LLM loop, fallback, audit)
        → Read/Compute tools | Propose tools (DRAFT + manager notify)
```

## HITL policy

| Tier | Behaviour |
|------|-----------|
| Read / Compute | Allowed automatically |
| Propose | Draft + manager notification; `requires_approval=true` |
| Execute | Never on agent allowlists (no silent price/PO/refund execution) |

Cancel, refund, and complaint tools always go through pending-approval backend endpoints.

## Modules

| Path | Role |
|------|------|
| `runtime/models.py` | `AgentRunRequest`, `AgentRunResult`, `ActionProposal`, `RiskTier` |
| `runtime/policy.py` | Tool registry + allowlist enforcement |
| `runtime/audit.py` | Structured run logs (no secrets/PII dumps) |
| `runtime/agent_runtime.py` | Unified `run()` entry |
| `runtime/wrap.py` | Ops agent helpers + default allowlists |
| `tools/backend_tools.py` | Customer chat tools (JWT-bound identity) |
| `agents/*_agent.py` | Thin public entry + rule fallback body |

## Agents

1. **Support chat** — `POST /agent/chat` (customer JWT)
2. **Demand forecast** — cron 2am IST
3. **Inventory reorder** — every 6h
4. **Churn prevention** — daily 10am IST
5. **Review response** — RabbitMQ + manual trigger
6. **Shift optimisation** — Sunday 8pm IST
7. **Kitchen coach** — nightly 11pm IST
8. **Dynamic pricing** — every 30m 9–22 IST (suggest only; never patches prices)

## Identity

- Customer chat: HS512 JWT (`JWT_SECRET`) verified in `auth.py`; tools use contextvars identity — never LLM-supplied customer IDs.
- Ops triggers: `AGENT_TRIGGER_API_KEY` header.
- Ops → platform backend: outbound `AGENT_TOKEN`.

## LLM configuration

- `LLM_MODEL` / `LLM_API_KEY` preferred (provider-agnostic), with `GOOGLE_API_KEY` fallback for existing deploys.
- Product/docs describe Google ADK + Gemini.

## Fallback

If the LLM path fails, rule-based agents still draft proposals and notifications so operations continue offline from the model provider.

## Out of scope (this program)

- Auto-execution of prices, POs, or campaigns without a manager
- Multi-ERP ingest / custom model training
