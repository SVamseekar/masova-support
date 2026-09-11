# Contributing to MaSoVa Agent

## Git workflow

Use **GitHub Flow**: feature branch → PR → squash merge → `main`.

Full detail (branch protection, CI check name `test`, prune after merge, commit style, archive tags):

**[GIT_WORKFLOW.md](./GIT_WORKFLOW.md)**

## Development setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/SVamseekar/masova-support.git
   cd masova-support
   ```

2. **Setup environment**
   ```bash
   make setup
   # or: python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && pip install -e .
   ```

3. **Configure secrets locally (never commit)**
   ```bash
   cp config/env.example .env
   # Set LLM_API_KEY or GOOGLE_API_KEY, JWT_SECRET, AGENT_TRIGGER_API_KEY, AGENT_TOKEN, BACKEND_URL
   ```

4. **Run tests**
   ```bash
   make test
   # or: pytest tests/ -q
   ```

## Project structure

```
masova-support/
├── src/masova_agent/    # Main agent code
├── tests/               # Test files
├── scripts/             # Shell scripts
├── docs/                # Documentation
├── config/              # Configuration files
└── .venv/               # Virtual environment (gitignored)
```

## Coding standards

### Python style

- Follow PEP 8 (line length 100, matching Black)
- Format: `make format` (Black). CI runs `black --check`.
- Lint/types: `make lint` (Black check, flake8, mypy)
- Repo hygiene: `make hygiene`
- Type hints for public functions
- Docstrings for public APIs

### Commit messages

- `feat:` / `feat(scope):` new features  
- `fix:` bug fixes  
- `docs:` documentation  
- `chore:` tooling / maintenance  
- `test:` tests  

No AI-tool `Co-Authored-By` trailers. No secrets in commits. Never commit `AGENTS.md` or `CLAUDE.md`.

### Testing

- Write tests for new features  
- Prefer unit tests that mock LLM and backend  
- Run the full suite before opening a PR  

### Agents / HITL

- Agents **propose** actions; they do **not** auto-write to production DB without manager approval  
- Tool functions: `async def` returning `dict` (ADK)  

## Making changes

1. Create a branch from `main` (`feature/`, `fix/`, `chore/`, `docs/`, `test/`)
2. Make changes; keep PRs small when possible  
3. Ensure CI job **`test`** is green  
4. Squash-merge the PR  
5. Prune local branch after merge (`git fetch --prune`)  

## Questions?

Open an issue for discussion.
