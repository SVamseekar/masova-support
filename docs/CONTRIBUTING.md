# Contributing to MaSoVa Agent

## Development Setup

1. **Clone the repository**
```bash
git clone <repository-url>
cd masova-support
```

2. **Setup environment**
```bash
make setup
```

3. **Configure API keys**
```bash
# Edit src/masova_agent/.env
GOOGLE_API_KEY=your_key_here
```

4. **Run tests**
```bash
make test
```

## Project Structure

```
masova-support/
├── src/masova_agent/    # Main agent code
├── tests/               # Test files
├── scripts/             # Shell scripts
├── docs/                # Documentation
├── config/              # Configuration files
└── .venv/              # Virtual environment
```

## Coding Standards

### Python Style
- Follow PEP 8
- Use Black for formatting: `make format`
- Run linters before committing: `make lint`
- Type hints for all functions
- Docstrings for public APIs

### Commit Messages
- Use conventional commits format:
  - `feat:` new features
  - `fix:` bug fixes
  - `docs:` documentation changes
  - `refactor:` code refactoring
  - `test:` test additions/changes

### Testing
- Write tests for new features
- Maintain test coverage above 80%
- Run full test suite before PR

## Making Changes

1. Create a feature branch
2. Make your changes
3. Run tests and linters
4. Commit with descriptive messages
5. Push and create PR

## Questions?

Open an issue for discussion!
