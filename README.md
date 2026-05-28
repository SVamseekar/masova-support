# MaSoVa Customer Support Agent

An intelligent customer support agent built with Google's Agent Development Kit (ADK) for the MaSoVa Restaurant Management System.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Google ADK](https://img.shields.io/badge/Google-ADK%201.25-green.svg)](https://github.com/google/adk-python)
[![License](https://img.shields.io/badge/license-Proprietary-red.svg)](LICENSE)

## 🎯 Overview

MaSoVa Intelligence is an AI-powered customer support assistant that provides:
- ✅ **User Verification**: Validates customers against the MaSoVa database
- ✅ **Order Tracking**: Real-time status updates for customer orders
- ✅ **Location Detection**: Automatic geolocation with smart caching
- ✅ **Customer Support**: Handles menu inquiries, orders, and general assistance

## 🚀 Quick Start

### Prerequisites

- Python 3.9-3.12 (3.13+ not supported by ADK yet)
- Google GenAI API key ([Get one here](https://makersuite.google.com/app/apikey))

### Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd masova-support

# Setup (creates venv, installs dependencies, creates .env)
make setup

# Edit .env and add your API key
nano src/masova_agent/.env
```

### Running the Agent

**Web UI (Recommended):**
```bash
make web
# Open http://127.0.0.1:8000
```

**Interactive Chat:**
```bash
make chat
```

**Run Tests:**
```bash
make test
```

## 📁 Project Structure

```
masova-support/
├── src/
│   └── masova_agent/          # Main agent code
│       ├── agent.py           # Core AI agent
│       ├── chat.py            # Interactive interface
│       └── .env               # API keys (not in git)
├── tests/                     # Test suite
│   ├── test_scenarios.py      # Automated tests
│   └── test_connection.py     # API connectivity test
├── scripts/                   # Shell scripts
│   ├── start-web.sh          # Launch web UI
│   ├── start-chat.sh         # Launch chat
│   └── run-tests.sh          # Run tests
├── docs/                      # Documentation
│   ├── ARCHITECTURE.md        # System design
│   ├── PROJECT_PHASES.md      # Development roadmap
│   └── CONTRIBUTING.md        # Contribution guide
├── config/                    # Configuration files
│   ├── env.example           # Environment template
│   └── logging.yaml          # Logging config
├── .venv/                     # Virtual environment
├── pyproject.toml            # Project metadata
├── requirements.txt          # Dependencies
├── Makefile                  # Command shortcuts
└── README.md                 # This file
```

## 💬 Usage Examples

### Example 1: User Identification
```python
from masova_agent import send_message

response = send_message("Hi, I'm Soura Vamseekar")
print(response)
```

**Output:**
```markdown
### 🛡️ MaSoVa System Briefing

**Identity:** Soura Vamseekar
**Role:** GOLD Member (1250 pts)
**Location:** 📍 Hyderabad, India

---
**📦 Order Status:**
**Chicken Biryani** (ORD-20260216-102) is **OUT_FOR_DELIVERY**.
```

### Example 2: Web Interface

```bash
make web
```

Then navigate to `http://127.0.0.1:8000` and interact through the beautiful ADK web UI.

## 🧪 Testing

**Run all tests:**
```bash
make test
```

**Run specific test:**
```bash
python tests/test_scenarios.py
```

**Test API connection:**
```bash
python tests/test_connection.py
```

## 🛠️ Development

**Install dev dependencies:**
```bash
make install-dev
```

**Format code:**
```bash
make format
```

**Run linters:**
```bash
make lint
```

**Clean generated files:**
```bash
make clean
```

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for detailed development guidelines.

## 📊 Architecture

The agent uses:
- **Google ADK**: Agent framework
- **Gemini 2.0 Flash**: LLM model
- **InMemoryRunner**: Session management
- **Tool-based design**: Modular functionality

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed system design.

## 🔧 Configuration

### Environment Variables

Create `src/masova_agent/.env`:

```env
# Required
GOOGLE_API_KEY=your_actual_api_key_here

# Optional
GOOGLE_GENAI_USE_VERTEXAI=0  # 0 for AI Studio, 1 for Vertex AI
```

### Mock Database

The current implementation uses in-memory mock data:

**Customer:**
- Name: Soura Vamseekar
- ID: CUST-001
- Tier: GOLD
- Points: 1250

**Order:**
- ID: ORD-20260216-102
- Item: Chicken Biryani
- Status: OUT_FOR_DELIVERY

**⚠️ Note:** Replace with MongoDB in Phase 2 (see [PROJECT_PHASES.md](docs/PROJECT_PHASES.md)).

## 📝 Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

## 🐛 Troubleshooting

**Error: "No module named 'google.adk'"**
```bash
make install
```

**Error: "GOOGLE_API_KEY not found"**
- Check `src/masova_agent/.env` exists
- Verify API key is set correctly

**Geolocation timeout:**
- Internet connectivity issue
- API might be down (falls back to "Encrypted")

**ADK Web shows no agents:**
- Run from project root: `make web` or `adk web src`
- Don't run from inside `src/` directory

## 🚧 Roadmap

**Current Version:** 0.1.0 (Phase 1 Complete)

**Next Steps:**
- [ ] MongoDB integration
- [ ] Menu management system
- [ ] Order placement functionality
- [ ] Payment processing
- [ ] Multi-language support
- [ ] Docker containerization
- [ ] CI/CD pipeline

See [PROJECT_PHASES.md](docs/PROJECT_PHASES.md) for complete roadmap.

## 📚 Resources

- [Google ADK Documentation](https://google.github.io/adk-docs/)
- [Gemini API Documentation](https://ai.google.dev/docs)
- [Google ADK Python Repository](https://github.com/google/adk-python)

## 📄 License

Internal project for MaSoVa Restaurant Management System.

## 👥 Contributors

- MaSoVa Development Team

---

**Questions or Issues?** Check [CONTRIBUTING.md](docs/CONTRIBUTING.md) or open an issue.
