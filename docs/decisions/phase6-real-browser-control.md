# Phase 6 Architectural Decisions: Chrome Browser Control & Extension Integration

## Context
Previous phases established backend agent sessions, tools, opportunity detection, CRM schemas, website research, and approved outreach draft generation. However, browser execution remained confined to mocked backend test harnesses. Phase 6 realizes the end-to-end control model with a real Chrome Extension (Manifest V3) connected over a local WebSocket gateway.

## Key Decisions

### 1. Chrome Extension as Execution Layer, FastAPI as Intelligence Layer
The Chrome extension is strictly an observation and execution runtime. It does not parse lead models, score opportunities, or generate copy. All business logic, safety rules, prompt-injection sanitization, and qualification remain centrally governed in FastAPI.

### 2. Manifest V3 Minimal Permissions
Requested only:
- `activeTab`: To inspect the user's explicitly active browsing tab.
- `tabs`: To open public research links and listen for page navigation.
- `storage`: To persist ephemeral pairing credentials and session state locally.
Omitted: `cookies`, `webRequestBlocking`, `management`, `debugger`.

### 3. Ephemeral Pairing Token Architecture
To avoid persisting permanent credentials or storing API keys inside the browser, the dashboard generates a 5-minute single-use pairing challenge (`TV-XXXX-XXXX`). The extension submits this code over HTTP to receive a scoped session token `tv_sess_*` that authenticates the WebSocket connection.

### 4. Human Approval Gating & Final Confirmation Boundary
Outreach execution requires two gates:
1. Backend gate: Draft must be in `APPROVED` status from Phase 5 review.
2. Extension popup gate: The extension displays the exact recipient, message text, and service recommendation with an explicit `[ Send ]` / `[ Cancel ]` button. Unconfirmed or cancelled messages are never transmitted.

### 5. Uncertain Delivery Safeguard
If an outreach action is triggered on Instagram or Reddit and the DOM shifts unexpectedly without explicit success confirmation, the status transitions to `DELIVERY_UNKNOWN` and draft status updates to `NEEDS_REVIEW`. Under no circumstances is automated retry attempted.

### 6. Strict Anti-Scraping / Anti-Evasion Policy
No stealth libraries, no fingerprint spoofing, no CAPTCHA solving. If a platform challenges access, the agent transitions to `BLOCKED` or `WAITING_FOR_USER` immediately.
