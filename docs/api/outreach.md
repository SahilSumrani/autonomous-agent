# Outreach API Reference

## Base Path: `/api/v1/leads`

All requests require the `X-Organization-ID` header.

### Endpoints

- `POST /{lead_id}/outreach/generate`  
  Generates up to 3 structured, evidence-backed variants (`A`, `B`, `C`).

- `GET /{lead_id}/outreach`  
  Lists all outreach drafts for the lead.

- `GET /{lead_id}/outreach/{draft_id}`  
  Retrieves a single draft with associated evidence items and approval records.

- `POST /{lead_id}/outreach/{draft_id}/validate`  
  Validates draft text against evidence and recalculates quality score.

- `POST /{lead_id}/outreach/{draft_id}/approve`  
  Human approval gate. Transitions draft and lead to `APPROVED`. Does NOT perform external sending.

- `POST /{lead_id}/outreach/{draft_id}/reject`  
  Rejects draft with an auditable reason.

- `POST /{lead_id}/outreach/{draft_id}/regenerate`  
  Marks current draft `SUPERSEDED` and generates a new draft with preferences (`shorter`, `more conversational`, etc.).

- `GET /{lead_id}/outreach/history`  
  Returns full outreach history, including drafts, approvals, and attempts.
