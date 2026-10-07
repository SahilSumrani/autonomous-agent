# Research & Website Intelligence API

All endpoints require multi-tenant authentication via `X-Organization-ID` header.

## Endpoints

### 1. Initiate Lead Website Research
`POST /api/v1/leads/{lead_id}/research`
- Payload: `{"website_url": "https://example.com", "force_recheck": false, "pages_data": [...]}`
- Status: `201 Created`
- Response: `WebsiteResearchResponse`

### 2. Get Latest Lead Research
`GET /api/v1/leads/{lead_id}/research`
- Status: `200 OK`
- Response: `WebsiteResearchResponse`

### 3. List Research History
`GET /api/v1/leads/{lead_id}/research/history`
- Status: `200 OK`
- Response: `List[WebsiteResearchResponse]`

### 4. Get Audited Pages
`GET /api/v1/leads/{lead_id}/research/pages`
- Status: `200 OK`
- Response: `List[WebsitePageResearchResponse]`

### 5. Get Technology Stack
`GET /api/v1/leads/{lead_id}/research/technology`
- Status: `200 OK`
- Response: `TechnologyStackResponse`

### 6. Get Audit Scores
`GET /api/v1/leads/{lead_id}/research/audit`
- Status: `200 OK`
- Response: `WebsiteAuditResponse`

### 7. Get Opportunities Breakdown
`GET /api/v1/leads/{lead_id}/research/opportunities`
- Status: `200 OK`
- Response: `WebsiteOpportunityResponse`

### 8. Re-run Research
`POST /api/v1/leads/{lead_id}/research/re-run`
- Status: `201 Created`
- Response: `WebsiteResearchResponse`
