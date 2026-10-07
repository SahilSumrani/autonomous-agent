# User-Authorized Browser Research Agent (Phase 2)

## 1. Overview & Core Philosophy
The Browser Research Agent operates as a **human-supervised assistant** inside the user's active browser (e.g. Chrome Extension), rather than a mechanical bulk scraper.
The browser itself is the discovery environment where public content (Instagram Reels/Posts, Reddit community threads, public company websites) is observed, evaluated for client acquisition signals, synthesized into CRM leads, and transformed into personalized drafts requiring human approval.

## 2. Safety & Compliance Architecture
The agent strictly adheres to platform and legal boundaries:
- **Zero Stealth Automation**: No CAPTCHA bypass, no fingerprint spoofing, no anti-bot evasion.
- **Fail-Safe Stopping**: If a platform blocks access or triggers a security challenge, the agent halts immediately, shifts state to `BLOCKED`, and hands control to the user.
- **Zero Credential / Cookie Exposure**: Passwords, cookies, session storage, and private profile data are never extracted, logged, or persisted.
- **Human-in-the-Loop Gate**: All outbound comments, DMs, or emails require explicit human review via `ActionApproval`. Unapproved actions are rejected at the API layer with `403 Forbidden`.
- **Duplicate Contact Protection**: Re-contacting an already messaged recipient or lead is automatically blocked unless an explicit manual override is supplied.

## 3. Operational State Machine
Managed by `BrowserAgentStateMachine`:
```
  IDLE ──► OBSERVING ──► RESEARCHING ──► EVALUATING ──► LEAD_FOUND
               │               │              │             │
               │               │              ▼             ▼
               │               │          (No Lead)   RESEARCHING_PROFILE
               │               │                            │
               │               ▼                            ▼
               ├────────► PAUSED / BLOCKED          GENERATING_ACTION
               │                                            │
               ▼                                            ▼
           COMPLETED / FAILED                      WAITING_FOR_APPROVAL
                                                            │
                                                            ▼
                                                        EXECUTING
```

## 4. Controlled Browser Tool Registry
Located in `packages/agent_core/tools.py`:
- `open_page` (Risk: LOW, Perm: READ_ONLY)
- `navigate` (Risk: LOW, Perm: READ_ONLY)
- `read_page` (Risk: LOW, Perm: READ_ONLY)
- `find_text` (Risk: LOW, Perm: READ_ONLY)
- `scroll` (Risk: LOW, Perm: READ_ONLY)
- `click` (Risk: MEDIUM, Perm: USER_INTERACTION)
- `extract_visible_content` (Risk: LOW, Perm: READ_ONLY)
- `extract_links` (Risk: LOW, Perm: READ_ONLY)
- `request_user_approval` (Risk: HIGH, Perm: SENSITIVE_ACTION, Requires Approval: YES)

## 5. Opportunity Detection & Personalization
1. **OpportunityDetector** (`services/api/app/agents/discovery/opportunity_detector.py`):
   Deterministic intent matching against verified buying signals:
   - `BUSINESS_LAUNCH` (E-commerce / Storefront needs)
   - `WEBSITE_REQUEST` / `WEBSITE_REDESIGN` (Web development & performance rebuilds)
   - `APP_DEVELOPMENT_REQUEST` (Mobile application development)
   - `AI_AUTOMATION_REQUEST` (Operational agentic workflows)
   - `AGENCY_SEARCH` (Agency partnership needs)
2. **DraftGenerator** (`services/api/app/agents/personalization/draft_generator.py`):
   Synthesizes non-generic, observation-backed outreach:
   - Specific observation
   - Concrete TechVerse value proposition
   - Low-friction architectural question / CTA

## 6. Extension ↔ Gateway API Endpoints
All routes under `/api/v1/agent`:
- `POST /sessions` — Initialize user-authorized browser session
- `GET /sessions/{id}` — Fetch session status and active domain
- `POST /sessions/{id}/state` — Pause, resume, block, or stop session
- `POST /sessions/{id}/events` — Record auditable tool execution event
- `POST /sessions/{id}/observe` — Process visible page content, create CRM lead & signal, and generate approval gate
- `GET /tools` — List verified tools and risk definitions
- `GET /approvals` — List pending action approvals
- `POST /approvals/{id}/review` — Approve or reject draft
- `POST /approvals/{id}/execute` — Dispatch approved action (enforces `APPROVED` state and checks duplicate history)
