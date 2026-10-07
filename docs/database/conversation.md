# Conversation Intelligence Database Schema

## 1. Overview
Phase 7 adds 4 core tables via migration `0006_conversation_intelligence_tables.py` using UUID primary keys, UTC timestamps, and strict multi-tenant isolation (`organization_id`).

## 2. Table Specifications

### `conversation_threads`
Tracks ongoing multi-turn conversations associated with a CRM `lead`.
- `id` (UUID, PK)
- `organization_id` (UUID, FK -> organizations.id, ON DELETE CASCADE)
- `lead_id` (UUID, FK -> leads.id, ON DELETE CASCADE)
- `channel` (VARCHAR(50), default 'INSTAGRAM_DM')
- `external_thread_ref` (VARCHAR(255), nullable, indexed)
- `status` (VARCHAR(50), 'ACTIVE', 'WAITING_FOR_REPLY', 'NEEDS_HUMAN', 'CLOSED', 'BLOCKED')
- `current_intent` (VARCHAR(50), nullable)
- `sentiment` (VARCHAR(50), nullable)
- `sales_stage` (VARCHAR(50), default 'CONTACTED')
- `summary` (TEXT, rolling conversation summary)
- `last_message_at` (TIMESTAMPTZ, nullable)
- `metadata_json` (JSONB / JSON, nullable)
- `created_at`, `updated_at` (TIMESTAMPTZ)

### `conversation_messages`
Stores individual inbound and outbound messages with prompt-injection defense sanitization.
- `id` (UUID, PK)
- `organization_id` (UUID, FK -> organizations.id, ON DELETE CASCADE)
- `thread_id` (UUID, FK -> conversation_threads.id, ON DELETE CASCADE)
- `direction` (VARCHAR(20), 'INBOUND', 'OUTBOUND')
- `author_type` (VARCHAR(20), 'PROSPECT', 'AGENT', 'USER')
- `content` (TEXT, original text)
- `sanitized_content` (TEXT, defanged content)
- `source_url` (VARCHAR(2048), nullable)
- `external_message_ref` (VARCHAR(255), nullable, indexed for idempotency)
- `delivery_status` (VARCHAR(50), 'RECEIVED', 'DRAFTED', 'APPROVED', 'SENT', 'DELIVERY_UNKNOWN', 'FAILED')
- `evidence` (TEXT, nullable)
- `metadata_json` (JSONB / JSON, nullable)
- `created_at`, `updated_at` (TIMESTAMPTZ)

### `conversation_reply_drafts`
Stores AI-generated candidate reply variants.
- `id` (UUID, PK)
- `organization_id` (UUID, FK -> organizations.id, ON DELETE CASCADE)
- `thread_id` (UUID, FK -> conversation_threads.id, ON DELETE CASCADE)
- `in_reply_to_message_id` (UUID, FK -> conversation_messages.id, ON DELETE SET NULL)
- `variant` (VARCHAR(20), 'DIRECT', 'CONVERSATIONAL', 'INSIGHT_LED')
- `objective` (VARCHAR(50))
- `body` (TEXT)
- `quality_score` (INT, 0-100)
- `confidence` (FLOAT)
- `status` (VARCHAR(50), 'DRAFT', 'VALIDATED', 'READY_FOR_APPROVAL', 'APPROVED', 'REJECTED')
- `evidence_text` (TEXT, nullable)
- `risk_flags` (JSONB / JSON, nullable)
- `requires_human_approval` (BOOLEAN, default TRUE)
- `metadata_json` (JSONB / JSON, nullable)

### `conversation_approvals`
Tracks explicit human approval reviews for replies.
- `id` (UUID, PK)
- `organization_id` (UUID, FK -> organizations.id, ON DELETE CASCADE)
- `thread_id` (UUID, FK -> conversation_threads.id, ON DELETE CASCADE)
- `reply_id` (UUID, FK -> conversation_reply_drafts.id, ON DELETE CASCADE)
- `status` (VARCHAR(50), 'PENDING', 'APPROVED', 'REJECTED', 'EXECUTED')
- `reviewer_id` (VARCHAR(255), nullable)
- `reviewed_at` (TIMESTAMPTZ, nullable)
- `decision_reason` (TEXT, nullable)
- `created_at` (TIMESTAMPTZ)
