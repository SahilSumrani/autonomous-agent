# CRM Core Architecture (Phase 1)

## 1. Multi-Tenancy Design
Every CRM entity is strictly partitioned by `organization_id`.
All repository queries and service operations require `org_id` context.
The API layer enforces tenant scoping via the `X-Organization-ID` header dependency in `services/api/app/api/v1/dependencies/auth.py`.

## 2. Deterministic Normalization Rules
Located in `services/api/app/services/normalization.py`:
- **Domain**: Strips protocols (`http://`, `https://`), ports, query parameters, trailing slashes, and leading `www.` while preserving critical subdomains (e.g., `app.example.com`).
- **Email**: Strips leading/trailing whitespace and enforces lowercase formatting.
- **Company Name**: Strips punctuation, collapses repeated whitespace, and safely removes trailing legal designations (`Inc`, `LLC`, `Ltd`, `Corp`).
- **Profile URL**: Enforces HTTPS, strips tracking arguments (`utm_*`, `igsh`, `fbclid`), normalizes domains, and preserves unique user path routes.
- **Username**: Strips leading `@`, whitespace, and normalizes casing.
- **Phone**: Preserves international `+` prefix and strips formatting characters (`(`, `)`, `-`, spaces).

## 3. Deduplication Hierarchy
Located in `services/api/app/services/deduplication.py`:
Matching hierarchy enforces the following strict order:
1. **Exact Normalized Domain** (Confidence 1.0)
2. **Exact Normalized Profile URL** (Confidence 0.95)
3. **Verified Email** (Confidence 0.90)
4. **Exact Normalized Company Name** (Confidence 0.75 — exact match only, never fuzzy/guess-based).

Similar but distinct names (e.g., `ABC Technologies` vs `ABC Technology`) are never merged automatically.

## 4. Pipeline State Machine
Valid transitions defined in `packages/shared_types/crm.py`:
- `NEW` -> `QUALIFIED`, `LOST`
- `QUALIFIED` -> `RESEARCHED`, `OUTREACH_READY`, `LOST`
- `RESEARCHED` -> `OUTREACH_READY`, `LOST`
- `OUTREACH_READY` -> `APPROVED`, `LOST`
- `APPROVED` -> `CONTACTED`, `LOST`
- `CONTACTED` -> `REPLIED`, `MEETING`, `LOST`
- `REPLIED` -> `MEETING`, `PROPOSAL`, `LOST`
- `MEETING` -> `PROPOSAL`, `WON`, `LOST`
- `PROPOSAL` -> `WON`, `LOST`
- `LOST` -> `NEW`, `QUALIFIED` (Reactivation)

All transitions trigger an immutable `PipelineEvent` record ensuring a complete audit log.
