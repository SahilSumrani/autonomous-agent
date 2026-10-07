# CRM Database Schema Documentation (Phase 1)

## 1. Entity Relationship Overview

```
 Organizations (1) ───< Users (N)
        │
        ├───< Companies (N) ───< Contacts (N)
        │          │                 │
        │          └─────┐     ┌─────┘
        │                │     │
        ├───< Leads (N) ─┴─────┘
        │       │
        │       ├───< LeadSignals (N)
        │       └───< PipelineEvents (N)
        │
        └───< LeadSources (N)
```

## 2. Core Entities & Constraints

### `organizations`
- Primary workspace boundary for multi-tenant isolation.
- `id`: UUID (PK)
- `name`: VARCHAR(255)
- `slug`: VARCHAR(255) (UNIQUE, INDEX)
- `created_at`, `updated_at`: TIMESTAMPTZ

### `users`
- Team members and system operators.
- `organization_id`: UUID (FK -> organizations.id, ON DELETE CASCADE)
- `email`: VARCHAR(255)
- `full_name`: VARCHAR(255)
- `role`: VARCHAR(50) (OWNER, ADMIN, MEMBER, VIEWER)
- `is_active`: BOOLEAN
- Unique Constraint: `(organization_id, email)`

### `companies`
- Target business accounts discovered or researched.
- `organization_id`: UUID (FK -> organizations.id, ON DELETE CASCADE)
- `name`: VARCHAR(255)
- `normalized_name`: VARCHAR(255) (INDEX)
- `domain`: VARCHAR(255)
- `normalized_domain`: VARCHAR(255) (INDEX)
- `status`: VARCHAR(50) (ACTIVE, INACTIVE, UNKNOWN)
- Composite Index: `(organization_id, normalized_domain)`, `(organization_id, normalized_name)`

### `contacts`
- Individual prospects, decision-makers, founders, or influencers.
- `organization_id`: UUID (FK -> organizations.id, ON DELETE CASCADE)
- `company_id`: UUID (FK -> companies.id, ON DELETE SET NULL)
- `email`: VARCHAR(255) (INDEX)
- `email_verified`: BOOLEAN
- `instagram_username`: VARCHAR(100) (INDEX)
- `linkedin_url`: VARCHAR(1024) (INDEX)
- `reddit_username`: VARCHAR(100) (INDEX)
- Composite Index: `(organization_id, email)`

### `lead_sources`
- Acquisition channel/origin definitions.
- `organization_id`: UUID (FK -> organizations.id, ON DELETE CASCADE)
- `source_type`: VARCHAR(50) (INSTAGRAM, REDDIT, WEB, SEARCH, DIRECTORY, MANUAL, OTHER)
- `source_name`: VARCHAR(255)
- `external_id`: VARCHAR(255)

### `leads`
- Central client acquisition opportunity record.
- `organization_id`: UUID (FK -> organizations.id, ON DELETE CASCADE)
- `company_id`: UUID (FK -> companies.id, ON DELETE SET NULL)
- `contact_id`: UUID (FK -> contacts.id, ON DELETE SET NULL)
- `source_id`: UUID (FK -> lead_sources.id, ON DELETE SET NULL)
- `status`: VARCHAR(50) (NEW, QUALIFIED, RESEARCHED, OUTREACH_READY, APPROVED, CONTACTED, REPLIED, MEETING, PROPOSAL, WON, LOST)
- `lead_type`: VARCHAR(50) (COMPANY, INDIVIDUAL, FOUNDER, CREATOR, FREELANCER, OTHER)
- `intent_score`: INT (CHECK: 0 <= score <= 100)
- `qualification_score`: INT (CHECK: 0 <= score <= 100)
- `overall_score`: INT (CHECK: 0 <= score <= 100)
- Composite Indexes: `(organization_id, status)`, `(organization_id, overall_score)`, `(organization_id, profile_url)`

### `lead_signals`
- Detected buying intent or need indicators.
- `lead_id`: UUID (FK -> leads.id, ON DELETE CASCADE)
- `signal_type`: VARCHAR(100)
- `confidence`: FLOAT (CHECK: 0.0 <= confidence <= 1.0)
- `evidence`: TEXT
- `detected_at`: TIMESTAMPTZ

### `pipeline_events`
- Immutable historical audit log of status transitions.
- `lead_id`: UUID (FK -> leads.id, ON DELETE CASCADE)
- `old_status`: VARCHAR(50)
- `new_status`: VARCHAR(50)
- `actor_type`: VARCHAR(50) (USER, SYSTEM, AGENT)
- `actor_id`: VARCHAR(255)
- `reason`: TEXT
- `created_at`: TIMESTAMPTZ (INDEX)
