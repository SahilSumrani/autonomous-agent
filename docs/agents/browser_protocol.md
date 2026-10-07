# Browser Gateway Protocol Specification

## Message Transport
The Chrome extension connects to FastAPI via WebSocket:
```text
ws://localhost:8000/api/v1/agent/browser/ws?token=<session_token>
```
Authentication requires a short-lived token acquired via pairing challenge exchange. Unauthenticated or expired connections are closed immediately (`WS 1008 Policy Violation`).

## Command Envelope
Every command from FastAPI to the Chrome Extension conforms to:

```json
{
  "frame_type": "COMMAND",
  "command": {
    "command_id": "123e4567-e89b-12d3-a456-426614174000",
    "session_id": "123e4567-e89b-12d3-a456-426614174001",
    "type": "READ_PAGE",
    "payload": {
      "include_links": true
    },
    "issued_at": 1728345600.0,
    "expires_at": 1728345630.0,
    "correlation_id": "cor_abc123"
  }
}
```

### Supported Command Types
- `OPEN_PAGE`: Open new tab with URL.
- `NAVIGATE`: Navigate current tab to verified safe public URL.
- `READ_PAGE`: Extract sanitised visible text, headings, and metadata.
- `FIND_TEXT`: Check if keyword or phrase exists in viewport.
- `SCROLL`: Scroll viewport down, up, or to bottom.
- `CLICK`: Structured element click using `ClickTarget` (by text, selector, or element id).
- `EXTRACT_VISIBLE_CONTENT`: Detailed content block extraction.
- `EXTRACT_LINKS`: Extract verified outbound HTTP/HTTPS links.
- `GET_PAGE_STATE`: Returns current tab URL, title, origin, page type, and interactivity.
- `EXECUTE_APPROVED_OUTREACH`: Dispatches approved message for popup user review and tab insertion.
- `PAUSE`: Cease active automated interactions.
- `RESUME`: Continue session operations.
- `STOP`: Terminate current session tasks.

## Result Envelope
Every command executed by the extension returns a structured result:

```json
{
  "frame_type": "RESULT",
  "payload": {
    "command_id": "123e4567-e89b-12d3-a456-426614174000",
    "session_id": "123e4567-e89b-12d3-a456-426614174001",
    "success": true,
    "status": "SUCCESS",
    "result": {
      "url": "https://www.instagram.com/p/DF...",
      "visible_text": "...",
      "headings": ["..."]
    },
    "error": null,
    "duration_ms": 42.5,
    "timestamp": 1728345601.0,
    "correlation_id": "cor_abc123"
  }
}
```

### Execution Status Values
- `SUCCESS`: Command completed normally.
- `FAILED`: Execution error (e.g. element not interactable).
- `BLOCKED`: Target URL is internal/private or page triggered security challenge.
- `WAITING_FOR_USER`: CAPTCHA, login prompt, or human review required.
- `DELIVERY_UNKNOWN`: External send action changed DOM but delivery confirmation could not be verified. Prevents automated duplicate retries.
- `EXPIRED`: Command timed out before execution started.
- `CANCELLED`: Session was stopped or paused by user.
