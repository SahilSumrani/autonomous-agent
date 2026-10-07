# Chrome Extension Architecture

## Monorepo Ownership
The Chrome extension is located in:
```text
apps/browser-extension/
```
Built using TypeScript 5.8 with esbuild and compliant with **Chrome Manifest V3**.

## Architecture & Component Hierarchy

```text
┌────────────────────────────────────────────────────────┐
│                   Chrome Browser                       │
│                                                        │
│   ┌────────────────┐            ┌──────────────────┐   │
│   │  Popup UI      │            │  Content Script  │   │
│   │  (Status,      │            │  (DOM Reader,    │   │
│   │   Pairing,     │            │   Safe Clicks,   │   │
│   │   Confirmation)│            │   Safety Guard)  │   │
│   └────────┬───────┘            └────────▲─────────┘   │
│            │                             │             │
│            │     chrome.tabs / runtime   │             │
│            └───────────────┬─────────────┘             │
│                            ▼                           │
│              ┌───────────────────────────┐             │
│              │ Background Service Worker │             │
│              │ - Connection Manager      │             │
│              │ - Command Router          │             │
│              │ - Session Manager         │             │
│              └─────────────┬─────────────┘             │
└────────────────────────────┼───────────────────────────┘
                             │
                  WebSocket (Short-Lived Token)
                             │
┌────────────────────────────▼───────────────────────────┐
│              FastAPI Browser Gateway                   │
│              /api/v1/agent/browser/ws                  │
└────────────────────────────────────────────────────────┘
```

## Directory Structure
- `src/background/`:
  - `service_worker.ts`: Main extension lifecycle coordinator.
  - `connection.ts`: Resilient WebSocket client with exponential backoff and heartbeat.
  - `command_router.ts`: Dispatches typed incoming commands to active tab content scripts.
  - `session_manager.ts`: Stores ephemeral tokens in `chrome.storage.local`.
- `src/content/`:
  - `content_script.ts`: Listens for background command messages.
  - `page_reader.ts`: Extracts sanitised visible text, headings, links, and forms.
  - `page_actions.ts`: Safe structured clicks (`ClickTarget`), scrolling, and input.
  - `safety_guard.ts`: Detects CAPTCHA, login challenges, and blocked states.
- `src/popup/`:
  - `popup.html` / `popup.ts` / `popup.css`: User status interface, pairing challenge input, active lead information, and manual confirmation card for outreach execution.
- `src/security/`:
  - `origin_policy.ts`: Blocks private IP ranges, loopback, cloud metadata (169.254.169.254), and browser internal schemes (`chrome://`, `file://`).
  - `permissions.ts`: Strips prompt-injection patterns and enforces read-only boundaries.
