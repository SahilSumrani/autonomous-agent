# CRM Core API Endpoints (Phase 1)

All endpoints prefixed with `/api/v1` and scoped via `X-Organization-ID` header.

## Companies
- `POST /api/v1/companies` — Create company with automated normalization and deduplication. Returns `409 Conflict` if existing domain/name matches.
- `GET /api/v1/companies` — Paginated list of companies. Supports `?search=...`, `?industry=...`, `?page=1`, `?page_size=25`.
- `GET /api/v1/companies/{company_id}` — Retrieve company details.
- `PATCH /api/v1/companies/{company_id}` — Update company attributes.

## Contacts
- `POST /api/v1/contacts` — Create contact with email/handle normalization and deduplication.
- `GET /api/v1/contacts` — Paginated list of contacts. Supports `?company_id=...`, `?search=...`, `?page=1`, `?page_size=25`.
- `GET /api/v1/contacts/{contact_id}` — Retrieve contact details.
- `PATCH /api/v1/contacts/{contact_id}` — Update contact attributes.

## Leads
- `POST /api/v1/leads` — Create sales lead. Verifies deduplication and creates initial creation `PipelineEvent`.
- `GET /api/v1/leads` — Paginated list of leads. Supports `?status=...`, `?lead_type=...`, `?source_id=...`, `?minimum_score=...`, `?maximum_score=...`, `?search=...`.
- `GET /api/v1/leads/{lead_id}` — Retrieve lead details.
- `PATCH /api/v1/leads/{lead_id}` — Update lead attributes.
- `DELETE /api/v1/leads/{lead_id}` — Delete lead.

## Pipeline & Status
- `POST /api/v1/leads/{lead_id}/status` — Transition lead status. Validates transition rules and generates immutable `PipelineEvent`. Returns `422 Unprocessable Content` if transition is invalid.
- `GET /api/v1/leads/{lead_id}/pipeline` — Retrieve immutable audit trail of pipeline events for a lead.

## Signals
- `GET /api/v1/leads/{lead_id}/signals` — List detected buying signals for a lead.
- `POST /api/v1/leads/{lead_id}/signals` — Add buying signal with confidence (0.0 to 1.0) and evidence.
