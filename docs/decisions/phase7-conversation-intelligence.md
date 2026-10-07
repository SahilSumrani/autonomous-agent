# Architecture Decision Record: Phase 7 Conversation Intelligence

## Context
Following successful initial outreach delivery in Phase 6, prospects respond with questions, pricing inquiries, meeting requests, or objections. The platform requires a multi-turn conversation intelligence engine that maintains context, categorizes intent, manages sales pipeline progression, drafts validated replies, and routes delivery through the Phase 6 Chrome Browser Gateway without autonomous business exposure.

## Key Decisions

1. **Deterministic Intent Classification First**:
   - Implemented 16 prioritized regex-based intent categories covering buying signals, inquiries, objections, and spam, backed by AI provider semantic fallback.
   - Prevents stochastic drift and ensures reliable classification for core conversational triggers.

2. **Inbound Defanging & Content Isolation**:
   - Inbound prospect text is sanitized before database storage and context assembly to neutralize prompt-injection attempts.

3. **Rolling Summaries**:
   - Rolling conversation summaries prevent exponential token expansion as threads grow, preserving key facts while bounding LLM context window size.

4. **Tri-Variant Generation with Channel Bounds**:
   - Generates up to 3 candidate styles (`DIRECT`, `CONVERSATIONAL`, `INSIGHT_LED`) bounded by channel limits (e.g. 50-700 chars for Instagram).

5. **Mandatory Human-in-the-Loop for Transmission**:
   - Zero autonomous sends. A human operator must explicitly review and approve a candidate reply. Dispatch delegates to the Phase 6 Chrome Browser Gateway.
