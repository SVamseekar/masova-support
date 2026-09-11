# Migration Guide - Repository Refactoring

**Date:** February 17, 2026
**Version:** 0.1.0

## What Changed?

The repository has been refactored into a professional Python project structure.

### Old Structure ❌
```
masova-support/
├── masova_agent/        # Everything was here
│   ├── agent.py
│   ├── chat.py
│   ├── test_*.py
│   └── .env
├── start-web.sh         # Scripts in root
├── README.md
└── requirements.txt
```

### New Structure ✅
```
masova-support/
├── src/masova_agent/    # Source code
│   ├── agent.py
│   ├── chat.py
│   └── .env
├── tests/               # Test files
│   ├── test_scenarios.py
│   └── test_connection.py
├── scripts/             # Shell scripts
│   ├── start-web.sh
│   ├── start-chat.sh
│   └── run-tests.sh
├── docs/                # Documentation
│   ├── ARCHITECTURE.md
│   └── CONTRIBUTING.md
├── config/              # Configuration
│   ├── env.example
│   └── logging.yaml
├── Makefile             # Command shortcuts
├── pyproject.toml       # Project metadata
└── README.md            # Updated docs
```

## Migration Steps

### 1. Update Your Commands

**Old Way:**
```bash
cd masova_agent
python3 chat.py
```

**New Way:**
```bash
make chat
# or
./scripts/start-chat.sh
```

### 2. Update Import Paths

If you have custom scripts importing the agent:

**Old:**
```python
from masova_agent.agent import send_message
```

**New:**
```python
from masova_agent.agent import send_message  # Still works!
# or
import sys
sys.path.insert(0, 'src')
from masova_agent.agent import send_message
```

### 3. Update Environment File

Your `.env` file has been copied to `src/masova_agent/.env`.
The template is now at `config/env.example`.

### 4. Use Makefile Commands

**Available commands:**
```bash
make help          # Show all commands
make install       # Install dependencies
make web           # Start web UI
make chat          # Start interactive chat
make test          # Run tests
make clean         # Clean up generated files
make format        # Format code with black
make lint          # Run linters
```

## What's New?

### ✨ Features Added

1. **Makefile**: Simple command interface
2. **pyproject.toml**: Modern Python packaging
3. **Documentation**:
   - `ARCHITECTURE.md` - System design
   - `CONTRIBUTING.md` - Development guide
   - `CHANGELOG.md` - Version history
4. **Configuration**: Centralized in `config/`
5. **Proper Testing**: Separated in `tests/`

### 🔧 Improvements

1. **Better organization**: Logical directory structure
2. **Professional packaging**: Can install with `pip install -e .`
3. **Development tools**: Linting, formatting, testing
4. **Clear documentation**: Easier onboarding

## Old Files

The old `masova_agent/` directory is still present for reference but will be removed in the next cleanup.

**What to do:**
- Review any custom changes you made
- Copy them to the new structure
- After verification, the old folder can be deleted

## Testing the Migration

```bash
# 1. Test web UI
make web

# 2. Test chat
make chat

# 3. Run tests
make test
```

All should work identically to before!

## Rollback (if needed)

If you need to go back to the old structure:

```bash
# The old files are still in masova_agent/
cd masova_agent
python3 chat.py  # Still works
```

## Questions?

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) or open an issue.
