# Browser Gateway API Reference

## Base Path
```text
/api/v1/agent/browser
```

All requests require tenant authorization header:
```text
X-Organization-ID: <uuid>
```

---

### `POST /challenge`
Generate a short-lived 5-minute single-use pairing challenge code.

**Response:**
```json
{
  "pairing_code": "TV-ABCD-1234",
  "expires_in_seconds": 300,
  "expires_at": "2026-10-07T17:30:00Z"
}
```

---

### `POST /pair`
Called by the extension with the challenge code to obtain a session credential.

**Request:**
```json
{
  "pairing_code": "TV-ABCD-1234",
  "browser_id": "chrome-desktop-v1",
  "client_version": "2.0.0"
}
```

**Response:**
```json
{
  "session_id": "123e4567-e89b-12d3-a456-426614174000",
  "session_token": "tv_sess_...",
  "status": "AUTHORIZED",
  "expires_at": "2026-10-08T17:30:00Z"
}
```

---

### `POST /revoke`
Revoke an active pairing token and disconnect the browser.

---

### `GET /status?session_id=<uuid>`
Returns active connection status, current page state, and current agent state.

---

### `POST /pause`
Pause active agent browser actions.

---

### `POST /resume`
Resume paused agent browser actions.

---

### `POST /stop`
Stop browser session and cancel all pending commands.

---

### `POST /execute-approved-outreach`
Gated execution of an approved Phase 5 outreach draft.
Enforces:
1. `APPROVED` draft status check
2. Duplicate send prevention
3. Channel recipient verification
4. Extension WebSocket dispatch
5. Human popup confirmation
6. Uncertain delivery protection (`DELIVERY_UNKNOWN` prevents automated retries)

---

### `WS /ws?token=<session_token>`
Real-time bi-directional command and observation stream between FastAPI and the Chrome Extension.
