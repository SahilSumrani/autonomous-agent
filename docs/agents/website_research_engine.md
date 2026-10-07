# Website Research Engine

## Overview
The **Website Research Engine** provides deep technical intelligence and opportunity discovery for leads identified through browser observation. It examines public websites via user-authorized browsing sessions, analyzes multi-page technical health, detects frameworks and technologies, and calculates deterministic opportunity scores.

## Research Pipeline
```text
Qualified Lead
      ↓
Resolve Website URL (SSRF-protected)
      ↓
Observe Page & Discover Internal Navigation
      ↓
Analyze Homepage & Priority Pages (/about, /services, /shop, etc.)
      ↓
Technology Detection (Frontend, CMS, Backend, E-Commerce, Analytics)
      ↓
Website Audit (Performance, Mobile UX, UX, SEO, Conversion)
      ↓
Calculate Website Opportunity Score (0–100)
      ↓
Generate Verifiable Lead Signals
      ↓
Recalculate Lead Score & Service Match
      ↓
Dispatch Domain Events
```

## Security & Anti-Bot Boundaries
- **No CAPTCHA Bypass**: If an anti-bot challenge occurs, status transitions to `BLOCKED`.
- **SSRF Defense**: Strict validation prohibits private, loopback, link-local, and reserved IP ranges (RFC 1918 / RFC 3927).
- **Prompt Injection Defense**: Public webpage text is treated strictly as untrusted data. Directive markers (e.g. `ignore previous instructions`, `reveal API key`) are filtered.
