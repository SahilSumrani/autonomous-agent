# Outreach Database Schema

## Tables Overview

### 1. `outreach_campaigns`
- Organizes batch campaigns across channels.
- Foreign key: `organization_id`.

### 2. `outreach_drafts`
- Stores generated message variants, subject, body, angle, service, and deterministic quality score.
- Foreign keys: `organization_id`, `lead_id`, `campaign_id` (optional).

### 3. `outreach_evidences`
- Verifiable claims directly supporting each draft.
- Foreign keys: `draft_id`, `organization_id`.

### 4. `outreach_approvals`
- Human approval gate audit trail (`PENDING`, `APPROVED`, `REJECTED`).
- Foreign keys: `organization_id`, `lead_id`, `draft_id`.

### 5. `outreach_attempts`
- Audit log of generation and duplicate checks (`RECORDED`, `BLOCKED`, `APPROVED`).
- Foreign keys: `organization_id`, `lead_id`, `draft_id` (optional).
