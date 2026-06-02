# Changelog

All notable changes to the MaSoVa Agent project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-02-17

### Added
- Initial project structure with proper Python packaging
- Core AI agent using Google ADK and Gemini 2.0 Flash
- User verification system with mock customer database
- Order tracking functionality
- Geolocation detection with caching (5s timeout)
- Session management with InMemoryRunner
- Interactive chat interface
- Automated test scenarios
- ADK Web UI support
- Shell scripts for easy startup (`start-web.sh`, `start-chat.sh`, `run-tests.sh`)
- Comprehensive README with setup instructions
- Environment variable management with `.env.example`
- Git ignore patterns for security
- Python requirements with pinned versions
- Project configuration files (`pyproject.toml`, `setup.py`)
- Logging configuration
- Architecture documentation

### Fixed
- Double bracket issue in virtual environment prompt
- Agent API method calls (corrected from `.run()` to proper ADK pattern)
- Unused imports cleanup
- Error handling improvements with specific exception types
- ADK web discovery issues

### Security
- Secured API keys in `.env` file
- Added `.gitignore` to prevent credential leaks
- Input validation on user queries
- Timeout protection on external API calls

## [Unreleased]

### Planned
- MongoDB integration for persistent storage
- Menu management system
- Order placement functionality
- Payment processing integration
- Multi-language support
- Unit tests with pytest
- CI/CD pipeline
- Docker containerization
