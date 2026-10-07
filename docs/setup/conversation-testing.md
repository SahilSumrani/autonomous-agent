# Conversation Intelligence Testing & Smoke Test Guide

## 1. Automated Test Suite
To execute the complete automated test suite across all phases:

```bash
# Run Phase 7 conversation intelligence tests
.\.venv\Scripts\pytest.exe tests/test_conversation_intelligence.py -v

# Run entire platform regression suite (Phases 0–7)
.\.venv\Scripts\pytest.exe -v
```

## 2. Manual Smoke Test Flow
1. **Initialize Backend**:
   - Ensure PostgreSQL and Redis are running.
   - Run `alembic upgrade head` to apply migration `0006_conversation_intelligence_tables`.
   - Start the API: `uvicorn services.api.app.main:app --reload --port 8000`.

2. **Establish Lead & Thread**:
   - `POST /api/v1/leads/{lead_id}/conversations` with `{"channel": "INSTAGRAM_DM"}`.
   - Note `thread_id`.

3. **Simulate Inbound Message**:
   - Send: `POST /api/v1/conversations/{thread_id}/messages/ingest`
     ```json
     {
       "content": "Hey! Loved your message. How much does a Shopify rebuild cost and how long does it take?",
       "author_type": "PROSPECT",
       "direction": "INBOUND"
     }
     ```

4. **Verify Analysis & Intent**:
   - Call `POST /api/v1/conversations/{thread_id}/analyze`.
   - Inspect intent: should be `PRICING_REQUEST`.
   - Inspect sales stage: should transition to `QUALIFIED_CONVERSATION`.

5. **Generate & Validate Replies**:
   - Call `POST /api/v1/conversations/{thread_id}/reply/generate`.
   - Review the 3 candidate drafts (`DIRECT`, `CONVERSATIONAL`, `INSIGHT_LED`).
   - Validate draft: `POST /api/v1/conversations/{thread_id}/replies/{reply_id}/validate`. Verify score >= 75 and status `READY_FOR_APPROVAL`.

6. **Approve & Dispatch**:
   - Approve draft: `POST /api/v1/conversations/{thread_id}/replies/{reply_id}/approve`.
   - Dispatch via browser gateway: `POST /api/v1/conversations/{thread_id}/replies/{reply_id}/send`.
   - Confirm delivery state persists as `SENT`.
