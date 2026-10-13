# Autonomous Browser Prospecting Agent

## 1. System Overview

The **Autonomous Browser Prospecting Agent** in TechVerse AI Client Acquisition OS v2 enables user-authorized, bounded, autonomous prospecting through the user's connected Chrome extension.

Instead of only passively observing individual browser tabs, the backend orchestrator actively drives the authorized browser session through a controlled, bounded state machine:

```
USER CONNECTS CHROME EXTENSION
              ↓
    CREATE PROSPECTING JOB
              ↓
    SELECT SOURCE ADAPTER
              ↓
  OPEN INITIAL DISCOVERY URL
              ↓
     READ VISIBLE CONTENT
              ↓
     CONTROLLED SCROLLING
              ↓
    DISCOVER CANDIDATES
              ↓
   DEDUPLICATE IDENTITY KEY
              ↓
  RESEARCH CANDIDATE PROFILE
              ↓
  EXTRACT TRUTHFUL BUSINESS INFO
              ↓
  DETECT BUYING-INTENT SIGNALS
              ↓
        QUALIFY LEAD
              ↓
    REAL WEBSITE RESEARCH
              ↓
     SCORE & MATCH SERVICE
              ↓
       UPSERT CRM LEAD
              ↓
GENERATE EVIDENCE-GROUNDED OUTREACH
              ↓
      READY_FOR_APPROVAL
              ↓
      STOP WORKFLOW
```

---

## 2. Core Safety Boundaries & Invariants

1. **Strict Human-In-The-Loop Outreach Boundary**:
   - The autonomous agent is strictly prohibited from autonomously sending messages, DMs, emails, comments, or form submissions.
   - All generated outreach drafts transition to `READY_FOR_APPROVAL` with an associated `ActionApproval` in status `PENDING`.
   - Execution strictly halts at `READY_FOR_APPROVAL`.

2. **No Stealth Automation or Platform Evasion**:
   - The agent operates in the user's normal authorized Chrome browser.
   - No fingerprint spoofing, cookie extraction, credential harvesting, or CAPTCHA bypass is permitted.
   - If Instagram, Reddit, Threads, or Cloudflare presents a CAPTCHA, login challenge, or rate-limit warning:
     - The orchestrator halts automated execution immediately.
     - Sets the job status to `BLOCKED`.
     - Records the exact challenge reason in `failure_reason`.
     - Emits `browser.security.challenge` and `prospecting.job.blocked`.
     - Allows the user to take over manually.

3. **Multi-Tenant and Session Isolation**:
   - Every browser command, observation, candidate, and job is strictly bound to `organization_id` and `agent_session_id`.
   - Cross-session or cross-organization command injection or observation leakage is prevented and rejected.

4. **Hard Budgets and Execution Limits**:
   - Each job defines bounded limits: `max_candidates`, `max_pages`, `max_scrolls`, `max_time_seconds`.
   - Scrolling terminates early when content hash does not reveal new information (no-new-content detection).

---

## 3. Data Architecture

### `prospecting_jobs`
- `id`: UUID (Primary Key)
- `organization_id`: UUID (Foreign Key -> `organizations.id`)
- `session_id`: Optional UUID (Foreign Key -> `agent_sessions.id`)
- `status`: `CREATED`, `QUEUED`, `RUNNING`, `PAUSED`, `WAITING_FOR_USER`, `BLOCKED`, `COMPLETED`, `FAILED`, `CANCELLED`
- `source`: `INSTAGRAM`, `REDDIT`, `THREADS`, `WEBSITE`, `WEB_SEARCH`
- `query`: Text query, subreddit, handle, or URL
- `target_service`: Optional service focus
- `target_industries`: JSON list of industries
- `target_geography`: Optional region filter
- `max_candidates`: Integer budget (default 10)
- `max_pages`: Integer budget (default 50)
- `max_scrolls`: Integer budget (default 5)
- `max_time_seconds`: Integer budget (default 1800)
- `statistics`: JSON dictionary of runtime metrics (`candidates_found`, `candidates_qualified`, `pages_visited`, `scrolls_performed`, `leads_created`, `outreach_drafted`)
- `failure_reason`: Text description if blocked or failed

### `prospect_candidates`
- `id`: UUID (Primary Key)
- `job_id`: UUID (Foreign Key -> `prospecting_jobs.id`)
- `organization_id`: UUID (Foreign Key -> `organizations.id`)
- `source`: Source platform
- `source_url`: URL where candidate was discovered
- `canonical_url`: Normalized canonical profile/site URL
- `platform`: `INSTAGRAM`, `REDDIT`, `THREADS`, `WEBSITE`, `WEB_SEARCH`
- `username_or_handle`: Social handle (`@handle`, `u/author`)
- `company_name`: Truthfully extracted company name
- `domain`: Normalized domain name
- `business_category`: Classified industry category
- `status`: `DISCOVERED`, `RESEARCHING`, `QUALIFIED`, `DISQUALIFIED`, `DUPLICATE`, `BLOCKED`, `FAILED`, `CONVERTED_TO_LEAD`
- `confidence`: Confidence score (0.0 - 1.0)
- `dedup_key`: Strong deduplication key (e.g. `instagram:handle`, `reddit:author`, `domain:example.com`)
- `linked_lead_id`: Foreign Key -> `leads.id`

### `prospect_observations`
- `id`: UUID (Primary Key)
- `job_id`: Foreign Key -> `prospecting_jobs.id`
- `candidate_id`: Foreign Key -> `prospect_candidates.id`
- `session_id`: Foreign Key -> `agent_sessions.id`
- `organization_id`: Foreign Key -> `organizations.id`
- `url`: Page URL
- `platform`: Source platform
- `page_title`: Page title
- `visible_text`: Observed text snippet (sanitized)
- `headings`: JSON list of headings
- `links`: JSON list of links
- `content_hash`: SHA-256 hash of visible text for deduplication

---

## 4. Source Adapters

All source adapters inherit from `ProspectingSource` (`services/api/app/agents/prospecting/sources/base.py`):

1. **`InstagramSource`**:
   - Entry URLs: `#hashtag` -> `/explore/tags/{hashtag}/`, `@handle` -> `/{handle}/`.
   - Security challenges: Detects login barriers, checkpoints, activity restrictions.
   - Candidate discovery: Extracts visible handles, bios, bio external links, post captions.
   - Dedup key: `instagram:{normalized_handle}`.

2. **`RedditSource`**:
   - Entry URLs: `r/{subreddit}` -> `/r/{subreddit}/`, search -> `/search/?q={query}`.
   - Security challenges: Detects bot verification, human checks, IP blocks.
   - Anti-false-positive filtering: Filters out student homework, freelancer self-promotions, casual queries.
   - Dedup key: `reddit:{normalized_author}` or `reddit_post:{post_id}`.

3. **`ThreadsSource`**:
   - Entry URLs: `@handle` -> `/@{handle}`, search queries.
   - Security challenges: Detects Instagram login walls and checkpoints.
   - Dedup key: `threads:{normalized_handle}`.

4. **`WebsiteSource`**:
   - Entry URLs: Target website homepage or domain.
   - Extracts company name from title, contact information, domain.
   - Dedup key: `domain:{normalized_domain}` (prevents duplicates when visiting `/about` and `/contact`).

5. **`WebSearchSource`**:
   - Entry URLs: Public search queries.
   - Extracts business result links, normalizes target domains.
   - Dedup key: `domain:{normalized_domain}`.

---

## 5. Business Extraction & Buying Intent

- **`BusinessExtractor`** (`services/api/app/agents/prospecting/extractor.py`):
  - Strictly derives company name, domain, social handle, business category, and public emails/phones from page content.
  - Never hallucinates missing data: returns `None` when details are unavailable.
  - Strips bogus placeholder emails (`test@example.com`, `user@domain.com`) and image extensions.

- **`SignalDetectionEngine`** (`services/api/app/agents/signals/engine.py`):
  - Categorizes signals into:
    - **Buying Intent**: `WEBSITE_REQUEST`, `APP_DEVELOPMENT_REQUEST`, `AI_AUTOMATION_REQUEST`, `ECOMMERCE_OPPORTUNITY`, `REQUEST_FOR_SERVICE`.
    - **Business Growth**: `BUSINESS_LAUNCH`, `NEW_PRODUCT`, `BUSINESS_EXPANSION`, `GROWTH_SIGNAL`, `RECENT_FUNDING`.
    - **Hiring**: `HIRING_DEVELOPER`, `HIRING_DESIGNER`.
    - **Technical Opportunity**: `WEBSITE_OUTDATED`, `WEBSITE_SLOW`, `POOR_MOBILE_UX`, `WEAK_CONVERSION`, `WEAK_SEO`, `TECH_STACK_CHANGE`.
  - Disqualifying patterns reject competitor web dev agencies, freelancers, students, and job seekers.

---

## 6. Real Website Research

When a qualified prospect has a public domain:
- The browser agent navigates to the public website via `driver.open_page(target_url)`.
- Reads visible text and title.
- Hands real page observations to `ResearchService.execute_lead_website_research(lead_id, org_id, pages_data=...)`.
- If the website is unreachable, research is recorded truthfully with status `UNAVAILABLE` and zero confidence—never with fake findings.

---

## 7. Background Worker Architecture

Prospecting jobs do not block HTTP requests:
- `POST /api/v1/prospecting/jobs` creates the job and spawns a background task via `prospecting_worker.start_job_task(job_id, org_id, session_id)`.
- Background tasks are tracked in memory (`ProspectingWorker._running_tasks`) and persisted in PostgreSQL.
- If the backend restarts, pending jobs remain persisted and can be resumed cleanly.
- If the browser extension disconnects mid-job, the orchestrator sets job status to `WAITING_FOR_USER` without losing candidates or progress. Reconnecting the extension allows resuming via `POST /api/v1/prospecting/jobs/{job_id}/resume`.

---

## 8. REST API Endpoints

- `POST /api/v1/prospecting/jobs`: Create and optionally start a prospecting job.
- `GET /api/v1/prospecting/jobs`: List organization jobs with optional status filter.
- `GET /api/v1/prospecting/jobs/{job_id}`: Fetch job status, statistics, and bounds.
- `POST /api/v1/prospecting/jobs/{job_id}/start`: Start or queue an existing job.
- `POST /api/v1/prospecting/jobs/{job_id}/pause`: Pause an active job.
- `POST /api/v1/prospecting/jobs/{job_id}/resume`: Resume a paused or waiting job.
- `POST /api/v1/prospecting/jobs/{job_id}/cancel`: Cancel a job.
- `GET /api/v1/prospecting/jobs/{job_id}/candidates`: List candidates discovered during the job.
- `GET /api/v1/prospecting/jobs/{job_id}/observations`: List durable content observations recorded by the job.

---

## 9. Verification & Test Suite

All autonomous prospecting functionality is verified through comprehensive automated tests in `tests/test_autonomous_prospecting.py`:
- 10/10 tests pass across adapters, truthfulness, command driver, orchestrator loop, security challenge blocking, disconnect resilience, and REST APIs.
- 160/160 tests pass across the full repository test suite.
