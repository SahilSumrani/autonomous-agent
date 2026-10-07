# Database Schema: Website Research

## `website_research` Table
Stores high-level audit runs, overall scores, and detected stacks.

- `id`: UUID (PK)
- `organization_id`: UUID (FK `organizations.id`)
- `lead_id`: UUID (FK `leads.id`)
- `company_id`: UUID (FK `companies.id`, nullable)
- `website_url`: VARCHAR(512)
- `status`: VARCHAR(64) (`PENDING`, `RUNNING`, `COMPLETED`, `BLOCKED`, `FAILED`)
- `started_at`, `completed_at`: TIMESTAMPTZ
- `pages_analyzed`, `pages_failed`: INTEGER
- `technology_stack`: JSON
- `cms`, `frontend_framework`, `backend_technology`: VARCHAR(128)
- `analytics_tools`: JSON
- `cdn`, `ecommerce_platform`: VARCHAR(128)
- `website_health_score`, `performance_score`, `mobile_score`, `ux_score`, `seo_score`, `conversion_score`, `accessibility_score`: INTEGER (0–100)
- `opportunity_score`: INTEGER (0–100)
- `summary`: TEXT
- `positive_findings`, `negative_findings`, `recommendations`: JSON
- `confidence`: FLOAT

## `website_page_research` Table
Stores granular findings for individual visited pages.

- `id`: UUID (PK)
- `research_id`: UUID (FK `website_research.id`, cascade delete)
- `organization_id`: UUID (FK `organizations.id`)
- `url`: VARCHAR(1024)
- `page_type`: VARCHAR(64) (`HOMEPAGE`, `ABOUT`, `SERVICES`, `PRODUCTS`, `PRICING`, `SHOP`, `CONTACT`, `BLOG`, `OTHER`)
- `title`: VARCHAR(512)
- `content_summary`, `visible_text`: TEXT
- `has_cta`, `has_contact_form`, `has_phone`, `has_email`, `has_pricing`, `has_product_catalog`, `has_checkout`, `has_social_proof`: BOOLEAN
- `mobile_observations`, `ux_observations`, `seo_observations`, `performance_observations`, `conversion_observations`: JSON
- `created_at`: TIMESTAMPTZ
