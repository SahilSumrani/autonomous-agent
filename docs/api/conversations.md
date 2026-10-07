# Conversation Intelligence API Reference

All endpoints enforce tenant isolation (`X-Organization-ID` header required).

## Endpoints

### 1. `POST /api/v1/leads/{lead_id}/conversations`
Creates or retrieves an active conversation thread for a lead on a given channel (`INSTAGRAM_DM`, `REDDIT`, `LINKEDIN`, `EMAIL`).
- **Status**: `201 Created`
- **Request Body**:
  ```json
  {
    "channel": "INSTAGRAM_DM",
    "external_thread_ref": "ig_thread_123"
  }
  ```

### 2. `GET /api/v1/leads/{lead_id}/conversations`
Lists all conversation threads associated with a lead.

### 3. `GET /api/v1/conversations/{thread_id}`
Returns details of a conversation thread including rolling summary, current intent, sales stage, and messages.

### 4. `GET /api/v1/conversations/{thread_id}/messages`
Retrieves chronologically ordered messages for the thread.

### 5. `POST /api/v1/conversations/{thread_id}/messages/ingest`
Ingests an inbound prospect message or manual outbound message with idempotency check, defanging sanitization, and intent analysis.
- **Status**: `201 Created`
- **Request Body**:
  ```json
  {
    "content": "Hey! What are your rates for Shopify?",
    "author_type": "PROSPECT",
    "direction": "INBOUND",
    "external_message_ref": "msg_ext_999"
  }
  ```

### 6. `POST /api/v1/conversations/{thread_id}/analyze`
Analyzes thread context, classifies current intent, generates rolling summary, and evaluates sales stage transition.

### 7. `POST /api/v1/conversations/{thread_id}/reply/generate`
Formulates reply strategy and synthesizes up to 3 candidate variants (`DIRECT`, `CONVERSATIONAL`, `INSIGHT_LED`).
- **Response**: List of `ConversationReplyDraftResponse`.

### 8. `GET /api/v1/conversations/{thread_id}/replies`
Lists all candidate reply drafts for the thread.

### 9. `POST /api/v1/conversations/{thread_id}/replies/{reply_id}/validate`
Deterministically audits a reply draft against quality dimensions, channel length limits, and prohibited commitments.

### 10. `POST /api/v1/conversations/{thread_id}/replies/{reply_id}/approve`
Human approval gate. Records reviewer identity and marks draft as `APPROVED`.

### 11. `POST /api/v1/conversations/{thread_id}/replies/{reply_id}/reject`
Rejects draft with decision reason.

### 12. `POST /api/v1/conversations/{thread_id}/replies/{reply_id}/send`
Delegates approved reply transmission to Phase 6 Chrome Browser Gateway.
- Verifies draft status is `APPROVED`.
- Enforces recipient and thread context verification.
- Enforces delivery uncertainty protection.

### 13. `POST /api/v1/conversations/{thread_id}/close`
Closes the thread and transitions stage to `WON`, `LOST`, or `CLOSED`.
