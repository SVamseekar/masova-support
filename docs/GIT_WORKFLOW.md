# Git workflow (MaSoVa Support / Agent Service)

This repo uses **GitHub Flow** with a protected `main` and **squash merges**.

## Branching

| Prefix | Use |
|--------|-----|
| `feature/` | New behavior, agents, APIs |
| `fix/` | Bug fixes |
| `chore/` | Tooling, CI, deps, cleanup |
| `docs/` | Documentation only |
| `test/` | Test harness / fixtures |

1. Start from an up-to-date `main`:
   ```bash
   git checkout main
   git pull origin main
   git checkout -b feature/short-description
   ```
2. Open a PR targeting `main`.
3. Wait for the required CI check **`test`** (workflow job name) to pass.
4. **Squash merge** into `main` (only merge method enabled).
5. Head branch is **auto-deleted** on GitHub after merge. Prune locally:
   ```bash
   git checkout main
   git pull origin main
   git fetch --prune
   git branch -d feature/short-description   # if still present locally
   ```

## Branch protection (main)

- Pull request required (no direct push for normal work)
- **Required status check:** `test` (strict — branch must be up to date with `main`)
- Linear history (squash merges)
- No force-push, no branch deletion of `main`
- Conversation resolution required before merge
- Admins are enforced by the same rules
- Approving review count is **0** (solo maintainer); bar is **self-review + green CI**

## Commit messages

Use conventional prefixes (scope optional):

- `feat(...):` — new capability
- `fix(...):` — bug fix
- `chore(...):` — maintenance
- `test(...):` — tests
- `docs(...):` — documentation

Do **not** add `Co-Authored-By` trailers for AI coding tools (Claude, Cursor, Codex, Grok, Copilot, etc.). Dependabot merge trailers on GitHub are expected. Never rewrite published `main` history. If a personal feature branch must be rewritten, use `--force-with-lease`, never `--force`.

## Never commit

- `.env` / real secrets / API keys
- `AGENTS.md` / `CLAUDE.md` (local-only; gitignored)
- `.claude/`, `.cursor/`, `.codex/`, `.grok/`, and other AI-editor workspaces
- `docs/audit/` and other agent scratch directories
- Virtualenvs (`.venv/`), caches, coverage artifacts

Public docs and README describe **Gemini / Google ADK**. Do not put internal provider names in tracked docs or commit messages intended for public history.

## CI

- Workflow: `.github/workflows/ci.yml`
- Required check name: **`test`** (must stay this name — branch protection uses it)
- On pull requests and pushes to `main`: install from `requirements.txt`, repository hygiene, flake8 syntax/undefined-name checks, package import, unit tests (dummy env, no live LLM/backend), `pip-audit` (starlette 1.x CVEs ignored until ADK allows that upgrade — see `SECURITY.md`)
- Official Actions pinned to commit SHAs
- `permissions: contents: read`
- Concurrency cancels outdated runs on the same ref
- Full Black / flake8 / mypy are **not** required gates yet (they fail on the current tree). Do not skip the existing gates to keep CI green.

## Dependabot

Config: [`.github/dependabot.yml`](../.github/dependabot.yml)

| Ecosystem | Cadence | Grouping |
|-----------|---------|----------|
| `github-actions` | Weekly (Monday) | All Actions in one PR |
| `pip` | Weekly (Monday) | **Google AI stack** (`google-adk`, `google-genai`, related) in one PR; other **minor/patch** grouped; remaining **majors** individual |

- Commit prefix: `chore(deps):` (via `prefix: chore` + `include: scope`)
- Labels: `dependencies`, plus `github-actions` or `python` (create these labels if missing)
- Runtime install source of truth: **`requirements.txt`** (CI: `pip install -r requirements.txt` then `pip install -e . --no-deps`). Keep **`pyproject.toml` pins** aligned with those lower bounds.
- **`google-adk` + `google-genai` must move together** — ADK versions pin a genai range (e.g. ADK 1.28.x needs `google-genai>=1.64,<2`). Majors for both are ignored by Dependabot; upgrade deliberately in one PR.
- Also ignored majors: `redis`, `black` (noise / breaking).
- Prefer **squash-merge** only after CI `test` is green.
- **Security alerts** (GitHub → Security → Dependabot): treat as higher priority than routine bumps. Security floor today: `google-adk>=1.28.1`, `python-dotenv>=1.2.2`.
- After changing `dependabot.yml`, close conflicting ungrouped PRs; Dependabot will open fresh grouped PRs on the next schedule.

## Stale branches and archives

- Prefer auto-delete on merge; after older merges without auto-delete, remove remote branches only after verifying content is on `main` or intentionally abandoned.
- Unique WIP that is not merged may be preserved as an **archive tag** before branch delete:
  ```bash
  git tag archive/<name> <commit>
  git push origin archive/<name>
  git push origin --delete <branch>
  ```

### Known archive tags

- `archive/wip-agent-local-2026-07-09` — parked local agent/legacy snapshot from July 2026 (not on main). Inspect with `git show archive/wip-agent-local-2026-07-09`.

## Releases

See **[RELEASING.md](./RELEASING.md)**. Short version: SemVer tags `vMAJOR.MINOR.PATCH` from green `main`, changelog entry, annotated tag, GitHub Release from that tag. Never move or delete a published tag.

## Related docs

- [CONTRIBUTING.md](./CONTRIBUTING.md) — setup and coding standards
- [RELEASING.md](./RELEASING.md) — SemVer and GitHub Releases
- [RUNBOOK.md](./RUNBOOK.md) — operations
