# ADR-005: Website Intelligence Architecture & Deterministic Opportunity Scoring

## Status
Accepted

## Context
Qualified leads discovered via browser observation (Phase 2 & 3) require deep technical due diligence on their public websites to assess true client need and service fit. We needed an engine to:
1. Resolve and validate public websites without risk of SSRF or private intranet exposure.
2. Audit technical health, mobile UX, SEO, conversion funnels, and e-commerce readiness.
3. Compute an explainable, deterministic Opportunity Score (0–100) rather than allowing an LLM to hallucinate scores.
4. Synthesize findings into Phase 3 signals and score adjustments with an audit history.

## Decisions
1. **SSRF Network Boundary**: Enforce strict scheme validation (`http`/`https`) and reject loopback (`127.0.0.0/8`), RFC 1918 private subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), and link-local ranges before any network dispatch.
2. **Deterministic Opportunity Scoring**: Opportunity points are assigned strictly by audited health deficits (Performance: 20, Mobile: 15, UX: 15, SEO: 15, Conversion: 15, E-commerce: 10, Technology Modernization: 10).
3. **No Stealth / CAPTCHA Automation**: If an anti-bot challenge is encountered, mark research status as `BLOCKED`.
4. **Prompt Injection Treatment**: External webpage content is strictly treated as untrusted text; directive manipulation patterns are neutralized.
