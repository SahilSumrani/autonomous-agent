# TechVerse AI Client Acquisition OS — Chrome Browser Agent Extension

Production-grade Chrome Extension (Manifest V3) integrating the authorized user browser with the **TechVerse AI Client Acquisition OS V2** backend.

---

## 1. Architecture Overview

```text
User Chrome Browser
        ↕ (DOM / Content Script)
TechVerse AI Extension (MV3 Service Worker)
        ↕ (Authenticated WebSocket `ws://localhost:8000/api/v1/agent/browser/ws`)
FastAPI Browser Gateway (`services/api/app/agents/browser/gateway.py`)
        ↕
Agent Orchestrator (Phase 2 Discovery → Phase 3 Scoring → Phase 4 Research → Phase 5 Outreach)
        ↕
CRM + Human Approval Gate
```

---

## 2. Security Boundaries & Protections

- **Zero Credential Extraction**: The extension never requests or reads cookies, passwords, or persistent session storage.
- **SSRF Prevention**: All navigation commands are validated against loopback (`127.0.0.1`, `localhost`), private IPv4/IPv6 subnets, cloud metadata (`169.254.169.254`), and browser internal protocols (`chrome://`, `file://`, `about:`).
- **Anti-Bot / CAPTCHA Detection**: Automatically flags CAPTCHAs, bot challenges, or rate limits, transitioning to `BLOCKED` or `WAITING_FOR_USER`.
- **Human Approval Gate**: Outreach actions (`EXECUTE_APPROVED_OUTREACH`) require CRM approval (`APPROVED` status) AND explicit user confirmation in the extension popup before execution.
- **Uncertain Delivery Protection**: If page state changes but delivery cannot be verified with certainty, the draft transitions to `DELIVERY_UNKNOWN` without retrying.

---

## 3. Installation & Loading in Chrome

1. **Build the extension**:
   ```bash
   cd apps/browser-extension
   npm install
   npm run build
   ```
2. **Open Chrome**: Navigate to `chrome://extensions/`.
3. Enable **Developer mode** (toggle in upper right corner).
4. Click **Load unpacked**.
5. Select the `apps/browser-extension/dist` directory (where `manifest.json` resides).
6. The **TechVerse AI Browser Agent** icon will appear in your Chrome toolbar.

---

## 4. Pairing with Local Backend

1. Start your FastAPI server on `http://localhost:8000`.
2. Generate a pairing challenge via API:
   ```bash
   curl -X POST http://localhost:8000/api/v1/agent/browser/challenge -H "X-Organization-ID: <ORG_ID>"
   ```
   Or click **Connect Chrome** in the TechVerse OS dashboard.
3. Open the extension popup in Chrome and enter the pairing code (e.g., `TV-XXXX-XXXX`).
4. Click **Connect**. The status pill will turn green: **CONNECTED**.

---

## 5. Development & Testing

```bash
# Typecheck TypeScript source
npm run typecheck

# Run unit tests
npm run test

# Rebuild bundles
npm run build
```
