# TechVerse AI Client Acquisition OS (Autonomous Agent)

A production-grade, local-first **Autonomous Client Acquisition Operating System** that discovers genuine client opportunities across social platforms (Threads, LinkedIn, Reddit) and the public web, detects commercial buying intent, audits websites, qualifies leads deterministically, drafts personalized outreach, and surfaces discoveries on a real-time reactive dashboard.

---

## 🏗️ Architecture & How It Works

```
                                 TECHVERSE AI
                            CLIENT ACQUISITION OS
                                      │
                                      ▼
                        AUTONOMOUS TASK ORCHESTRATOR
                                      │
            ┌─────────────────────────┼─────────────────────────┐
            │                         │                         │
            ▼                         ▼                         ▼
   CHROME EXTENSION AGENT      SIGNAL DETECTION       WEBSITE RESEARCH
 (Interactive browser tab:    (18 intent types,      (Technical stack,
  Threads / LinkedIn / Web)    urgency scoring,        performance, UX,
                               anti-false positive)    contact extraction)
            │                         │                         │
            └─────────────────────────┼─────────────────────────┘
                                      ▼
                         3-TIER QUALIFICATION GATE
               ┌──────────────────────┴──────────────────────┐
               ▼                                             ▼
          QUALIFIED                                   REVIEW_REQUIRED
   (Explicit buying intent +                    (Ambiguous commercial signal,
    verified attributable source)                incomplete timeframe, or review)
               │
               ▼
     CRM LEAD & OUTREACH DRAFT
               │
               ▼
      HUMAN APPROVAL GATE ──► [Zero Autonomous Spam / Strict Operator Control]
               │
               ▼
    REAL-TIME WEB DASHBOARD (http://localhost:8000/dashboard)
```

### 1. Browser Research Agent
- Operates a dedicated Chrome tab via an authorized browser extension over secure WebSockets.
- Executes real, visible scrolling, query entry, pagination, and DOM content reading.
- Scrubs UI artifacts (`Follow`, `Like`, `Reply`, `Repost`, `Share`, audio notices) at both the extension and server ingestion layers.

### 2. Intent & Signal Detection Engine
- Analyzes text with deterministic keyword taxonomies across 18 signal types (e.g. `WEBSITE_REQUEST`, `APP_DEVELOPMENT_REQUEST`, `AI_AUTOMATION_REQUEST`, `HIRING_DEVELOPER`).
- **Anti-False Positive Filter**: Immediately identifies and filters out job seekers (`#opentowork`), student homework projects, competitors, and developers advertising their own services.
- **Disallowed Domain Safeguard**: Never treats public email providers (`gmail.com`, `yahoo.com`, `outlook.com`) or placeholders (`example.com`, `localhost`) as business websites.

### 3. Three-Tier Lead Qualification
- **`QUALIFIED`**: Verified explicit commercial buying intent with an attributable identity and direct post/profile URL.
- **`REVIEW_REQUIRED`**: Potential business opportunity with low confidence or ambiguous timeframe. These remain safely in review and are **never** auto-converted to CRM leads.
- **`DISQUALIFIED`**: Competitors, students, generic profiles, or unrelated posts.

### 4. Human-in-the-Loop Outreach & Safety
- **Zero Automated Outreach**: All outreach drafting halts at the human approval gate.
- No cold outreach messages are ever dispatched without explicit human authorization.

---

## 📁 Repository Structure

```
autonomous-agent/
├── apps/
│   ├── browser-extension/           # Chrome Extension (TypeScript, Manifest V3)
│   │   ├── src/background/          # Service worker & command router
│   │   ├── src/content/             # Content script & page reader / DOM cleaner
│   │   └── src/popup/               # Extension popup for pairing authorization
│   └── web/                         # Real-time WebSocket Dashboard (HTML/CSS/JS)
├── database/
│   └── migrations/                  # Alembic database migrations
├── packages/
│   ├── agent_core/                  # AI Provider Abstraction (Groq / Ollama / Local)
│   ├── config/                      # Settings & environment configuration
│   └── shared_types/                # Pydantic schemas, enums & shared contracts
├── services/
│   └── api/
│       └── app/
│           ├── agents/              # Orchestrator, sources (Threads, LinkedIn, Web)
│           ├── api/v1/              # FastAPI endpoints & WebSocket streaming
│           ├── core/                # Database engines, redis, auth, & logging
│           ├── models/              # SQLAlchemy models (CRM, Prospecting, Candidates)
│           └── services/            # Normalization, Lead scoring, CRM, Outreach
├── tests/                           # Pytest regression and integration suites
├── Dockerfile                       # Production container definition
├── docker-compose.yml               # Multi-container orchestration (Postgres, Redis, API)
└── pyproject.toml                   # Python dependencies & build config
```

---

## 🚀 Quickstart & Setup

### Prerequisites
- **Python 3.11+**
- **Node.js 18+** & npm
- **Docker & Docker Compose** (recommended for Postgres & Redis)
- **Google Chrome** (for browser agent extension)

---

### Method A: Running with Docker Compose (Recommended)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/SahilSumrani/autonomous-agent.git
   cd autonomous-agent
   ```

2. **Configure Environment**:
   ```bash
   cp .env.example .env
   ```
   *(Update `.env` with your AI provider credentials, e.g. Groq or Ollama)*

3. **Start All Services**:
   ```bash
   docker compose up -d
   ```
   This spins up:
   - **PostgreSQL 16**: `localhost:5432`
   - **Redis 7**: `localhost:6379`
   - **FastAPI Core Backend**: `http://localhost:8000`

4. **Verify Backend Health**:
   ```bash
   curl http://localhost:8000/api/v1/health
   ```

---

### Method B: Running Locally (Native Python)

1. **Start Database & Cache via Docker**:
   ```bash
   docker compose up -d postgres redis
   ```

2. **Create Python Virtual Environment**:
   ```bash
   # Windows PowerShell:
   python -m venv .venv
   .\.venv\Scripts\activate

   # Linux / macOS:
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -e ".[dev]"
   ```

4. **Run Database Migrations**:
   ```bash
   alembic upgrade head
   ```

5. **Start the FastAPI Backend**:
   ```bash
   uvicorn services.api.app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

---

## 🧩 Chrome Extension Build & Pairing

1. **Install and Build the Extension**:
   ```bash
   cd apps/browser-extension
   npm install
   npm run build
   ```
   This compiles output bundles into `apps/browser-extension/dist/`.

2. **Load in Google Chrome**:
   - Open Chrome and navigate to `chrome://extensions/`.
   - Enable **Developer mode** (toggle in top-right).
   - Click **Load unpacked** and select the folder:
     `apps/browser-extension/dist`

3. **Pair the Extension**:
   - Open the Web Dashboard: `http://localhost:8000/dashboard`
   - Click **Generate Pairing Code** (or request via API):
     ```bash
     curl -X POST http://localhost:8000/api/v1/agent/browser/challenge
     ```
   - Click the extension icon in Chrome, enter the pairing code, and click **Connect**.
   - The status indicator in the dashboard will turn **🟢 Chrome Agent Connected**.

---

## 📊 Using the Dashboard & Running Autonomous Tasks

1. **Access the Dashboard**:
   Open `http://localhost:8000/dashboard` in your browser.

2. **Start an Autonomous Prospecting Task**:
   - Select Platform: `Threads`, `LinkedIn`, or `Public Web`.
   - Choose Target Service: `Website Redesign`, `Business Website`, `Mobile App Development`, or `AI Automation`.
   - Enter Search Query (e.g. `looking for web developer`).
   - Click **▶ Start Autonomous Task**.

3. **Monitor Live Telemetry**:
   - Watch the agent navigate, scroll, extract content cards, and evaluate intent in real-time.
   - Prospects appear instantly in the feed with:
     - Direct clickable **Post URL**
     - Verified **Publication / Observation Date**
     - **Country Evidence**
     - Color-coded **Status Pill** (`QUALIFIED`, `REVIEW_REQUIRED`, `DUPLICATE`, `DISQUALIFIED`)
     - Intent and Lead Scores

---

## 🧪 Running Tests

Execute the complete regression and verification test suite:

```bash
# Run all audit defect repair regression tests
pytest tests/test_audit_defect_repairs.py -v

# Run normalization, signals, and scoring tests
pytest tests/test_normalization.py tests/test_signals_and_scoring.py -v

# Run the full test suite
pytest
```

---

## 🛡️ Security, Safety & Compliance

- **No Scraping Bypass / Anti-Bot Hacks**: No CAPTCHA evasion, fingerprint spoofing, or credential stuffing.
- **Zero Credential Exfiltration**: The extension never reads or stores passwords, cookies, or auth tokens.
- **Human Approval Gate**: Zero outreach messages are ever sent autonomously.
- **Data Integrity**: Placeholders (`example.com`) and generic email providers (`gmail.com`) are strictly rejected from being recorded as company domains.

---

## 📄 License

MIT License. Designed and built by Sahil Sumrani.
