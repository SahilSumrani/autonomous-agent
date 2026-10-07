# ADR-006: Outreach Intelligence, Evidence Grounding, and Human Approval Gate

## Context
Mass outreach automation often yields generic, spammy, or hallucinated claims that harm brand reputation. TechVerse requires high-converting, personalized outreach grounded strictly in verifiable observations and technical website audits.

## Decisions
1. **Evidence Grounding**: Every factual reference must map directly to CRM sources, Phase 3 intent signals, or Phase 4 website audit findings.
2. **Deterministic Scoring**: Message quality is calculated on a 0–100 scale across 7 dimensions (Evidence, Personalization, Relevance, Service Alignment, Clarity, CTA, Tone). Messages scoring below 75 or violating length constraints are held in `NEEDS_REVIEW`.
3. **Approval Boundary**: Phase 5 stops strictly at `APPROVED`. No external messages are transmitted to Instagram, Reddit, or Email. Browser-driven sending is reserved for Phase 6.
4. **Duplicate Outreach Protection**: Existing approvals or past contacts block new draft generation unless explicitly overridden by an authorized user.
