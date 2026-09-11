# Contributing

Solo-maintained. Self-review plus green CI. No second human reviewer.

Do not add AI-tool `Co-Authored-By` trailers. Do not commit `.env`, `AGENTS.md`,
`CLAUDE.md`, or other local-only files.

## Setup

```bash
git clone https://github.com/SVamseekar/masova-support.git
cd masova-support
make setup
# or: python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && pip install -e .
cp config/env.example .env
# set LLM_API_KEY or GOOGLE_API_KEY, JWT_SECRET, AGENT_TRIGGER_API_KEY, AGENT_TOKEN, BACKEND_URL
make test
make lint    # black --check, flake8, mypy
make hygiene
```

## Branching

GitHub Flow. Branch from latest `main`: `feature/`, `fix/`, `chore/`, `docs/`, `test/`.

```bash
git checkout main && git pull origin main
git checkout -b feature/short-description
```

Open a PR to `main`. Required CI check name: **`test`**. Squash-merge. GitHub
auto-deletes the head branch. Then:

```bash
git checkout main && git pull origin main && git fetch --prune
git branch -d feature/short-description
```

`main` is protected: PR required, `test` must pass, linear history, no
force-push, no deleting `main`, conversation resolution required, admins
enforced, 0 approving reviews.

Never rewrite published `main`. Feature-branch rewrite only with
`--force-with-lease`.

## Commits

`feat:` `fix:` `docs:` `chore:` `test:` `ci:` `refactor:` (scope optional).

Never commit secrets, `.env`, caches, or agent scratch.

Public docs stay Gemini / Google ADK.

## Coding

- Line length 100 (Black). CI runs `black --check`, flake8, mypy.
- Agents **propose**; they do not auto-write the production DB.
- Tools: `async def` returning `dict`.

## CI

`.github/workflows/ci.yml` on PRs and `main`: hygiene, Black, flake8, mypy,
wheel, import, pytest (dummy env), pip-audit. See `SECURITY.md` for documented
starlette ignores.

## Dependabot

`.github/dependabot.yml` — weekly pip + GitHub Actions. `google-adk` and
`google-genai` move together. Squash-merge only when `test` is green.

## Releases

See [RELEASING.md](RELEASING.md).
