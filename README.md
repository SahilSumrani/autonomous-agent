# TechVerse AI Client Acquisition OS (V2)

A production-grade, local-first Client Acquisition Operating System designed to identify genuine business opportunities, qualify intent, research companies, perform deterministic website audits, score leads, draft hyper-personalized outreach, track conversations, and manage pipeline conversions.

---

## Architecture Overview

```
                         TECHVERSE AI
                    CLIENT ACQUISITION OS
                              │
                              ▼
                       ORCHESTRATOR
                              │
          ┌───────────────────┼────────────────────┐
          │                   │                    │
          ▼                   ▼                    ▼
   DISCOVERY SYSTEM     SIGNAL ENGINE       WEB RESEARCH
  (Instagram/Reddit/   (Intent Detection)   (Company/Tech/Audit)
   Public Web/Search)
          │                   │                    │
          └───────────────────┼────────────────────┘
                              ▼
                       LEAD QUALIFICATION & SCORING
                              │
                              ▼
                     PERSONALIZATION & DRAFT AGENT
                              │
                              ▼
                       HUMAN APPROVAL QUEUE
                              │
                              ▼
                    AUTHORIZED OUTREACH & CRM
```

---

## Monorepo Layout

```
techverse-client-os/
├── apps/
│   ├── web/                         # Next.js Dashboard (Frontend)
│   └── browser-extension/           # Chrome Extension
├── services/
│   ├── api/                         # FastAPI Core Backend
│   └── worker/                      # Redis-backed Background Worker
├── packages/
│   ├── shared-types/                # Shared Domain Schemas & Contracts
│   ├── agent-core/                  # AI Provider Abstraction (Ollama / OpenAI / Gemini)
│   ├── prompts/                     # Versioned Agent Prompts
│   ├── config/                      # Pydantic v2 Settings & Environment
│   └── event-contracts/             # Event Bus Schemas (Redis Pub/Sub)
├── database/
│   ├── migrations/                  # Alembic Async Migrations
│   ├── schema/                      # Normalized Table Definitions
│   └── seeds/                       # Seed Datasets
├── infrastructure/
│   ├── docker/                      # Production & Development Containers
│   └── monitoring/                  # Observability & Metrics
└── tests/                           # Unit, Integration & E2E Suites
```

---

## Quickstart (Local Development)

### 1. Prerequisites
- Python 3.11+ (Python 3.14 verified)
- PostgreSQL 16 (Local or via Docker Compose)
- Redis 7+ (Local or via Docker Compose)
- Ollama (for local-first AI inference)

### 2. Infrastructure Setup
To spin up local PostgreSQL and Redis:
```bash
docker compose up -d
```

### 3. Virtual Environment & Dependencies
```bash
# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\activate   # Windows

# Install dependencies
pip install -e .
```

### 4. Running Migrations
```bash
alembic upgrade head
```

### 5. Running the Backend API
```bash
uvicorn services.api.app.main:app --reload --port 8000
```
Interactive API docs available at `http://localhost:8000/docs`.

### 6. Running the Test Suite
```bash
pytest
```

### 7. Chrome Extension Build & Pairing
```bash
# 1. Build extension bundle
cd apps/browser-extension
npm install
npm run build

# 2. In Google Chrome:
# Navigate to chrome://extensions/ -> Enable 'Developer mode' -> 'Load unpacked' -> Select apps/browser-extension/dist

# 3. Request pairing challenge from backend:
curl -X POST http://localhost:8000/api/v1/agent/browser/challenge -H "X-Organization-ID: <org-uuid>"

# 4. Open extension popup in Chrome and enter the pairing code to authorize the session.
```

---

## Security & Compliance Rules
- **No Scraping Bypass**: No CAPTCHA evasion, stealth fingerprinting, or credential stuffing.
- **Zero Exfiltration**: Extension does not request cookies, passwords, or persistent session credentials.
- **Human in the Loop**: All outreach drafts require explicit human approval and final popup confirmation before transmission.
- **SSRF Hardened**: All website audit tools validate target IPs against RFC 1918 private ranges, loopback, and cloud metadata endpoints.
- **Zero Hallucination**: Every research and signal datapoint requires source, evidence, and confidence.
- **Uncertain Delivery Safe**: Ambiguous message delivery status transitions to `DELIVERY_UNKNOWN` without automated retry.

