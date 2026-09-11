# MaSoVa Support Agent

AI-powered customer support and ops agents for the MaSoVa restaurant platform, built with **Google ADK** and **Gemini**.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Google ADK](https://img.shields.io/badge/Google-ADK-green.svg)](https://github.com/google/adk-python)
[![CI](https://github.com/SVamseekar/masova-support/actions/workflows/ci.yml/badge.svg)](https://github.com/SVamseekar/masova-support/actions/workflows/ci.yml)

## Overview

- **Support chat** (`POST /agent/chat`) — JWT-authenticated, tool-using ADK agent (orders, menu, loyalty, complaints, cancel/refund *requests*)
- **7 ops agents** — demand forecast, inventory reorder, churn, review response, shifts, kitchen coach, dynamic pricing
- **Human-in-the-loop** — agents **propose** (DRAFT + manager notify); they do not auto-execute prices, POs, or refunds
- **Shared AgentRuntime** — policy, audit logs, rule-based fallbacks when the model is unavailable

See [AGENT_PLATFORM.md](AGENT_PLATFORM.md) for architecture,
[CAPABILITY_MAP.md](CAPABILITY_MAP.md) for tool ↔ platform APIs,
[RUNBOOK.md](RUNBOOK.md) for operations, and
[SMOKE.md](SMOKE.md) for live probes.

**Design:** industry-style vertical agents — secure identity, tool-grounded numbers, human approval proposals, rule fallbacks, contract-mapped APIs, audited runs, CI evals — not an omniscient autonomous platform brain.

## Quick start

### Prerequisites

- Python **3.9–3.12** (CI runs 3.12; container image is 3.11)
- Gemini / Google GenAI API key
- Optional: Redis (sessions), RabbitMQ (review events), MaSoVa backend

### Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
cp config/env.example .env
# set LLM_API_KEY or GOOGLE_API_KEY, JWT_SECRET, AGENT_TRIGGER_API_KEY, AGENT_TOKEN, BACKEND_URL
# templates: .env.example and config/env.example (keep in sync)
```

### Run API

```bash
uvicorn src.masova_agent.main:app --host 0.0.0.0 --port 8000 --reload
```

- Health: `GET /health`
- Chat: `POST /agent/chat` with `Authorization: Bearer <customer-jwt>`
- Ops: `POST /agents/{name}/trigger` with `X-Agent-Api-Key: <AGENT_TRIGGER_API_KEY>`

### Tests

```bash
pytest tests/ -q
# or: make test
make lint    # black --check, flake8, mypy
make hygiene
```

Unit tests mock HTTP and LLM; no live Redis/RabbitMQ/backend required. CI runs hygiene, Black, flake8, mypy, wheel build, pytest, and `pip-audit` on pull requests and `main`.

### Docker

If a `Dockerfile` is present in the repo, build/run via your standard image flow. Prefer the uvicorn command above for local development.

## Project layout

```text
src/masova_agent/
  agent.py              # Support chat ADK agent (canonical entry)
  auth.py               # JWT + trigger API key
  main.py               # FastAPI app (+ proposals list/resolve)
  runtime/              # AgentRuntime, policy, audit, ops_llm, proposals, metrics
  agents/               # Ops agents (thin wrappers + rule fallbacks)
  tools/backend_tools.py
  tools/ops_tools.py    # Ops READ/COMPUTE/PROPOSE tools
  scheduler/            # APScheduler (shares FastAPI event loop)
tests/                  # unit + tests/eval industry harness
.github/workflows/ci.yml
config/env.example
AGENT_PLATFORM.md       # architecture
CAPABILITY_MAP.md       # tool ↔ HTTP map
RUNBOOK.md SMOKE.md     # ops + live probes
```

## Auth model

| Endpoint | Auth |
|----------|------|
| `/agent/chat` | Customer JWT (`JWT_SECRET`, HS512) — same secret as platform core-service |
| `/agents/*/trigger` | `AGENT_TRIGGER_API_KEY` |
| Outbound backend | `AGENT_TOKEN` (ops agents) or customer JWT (chat tools) |

Customer tools never trust LLM-supplied customer IDs; identity is bound from the verified JWT.

## Releases

Semantic versions `vMAJOR.MINOR.PATCH`. See [RELEASING.md](RELEASING.md) and [CHANGELOG.md](CHANGELOG.md).

## Security

See [SECURITY.md](SECURITY.md). Do not open public issues for vulnerabilities.

## License

Proprietary — MaSoVa. See [LICENSE](LICENSE).
