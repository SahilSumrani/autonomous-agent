# Outreach Intelligence Engine

## Overview
The Outreach Intelligence Engine translates verified lead qualifications, CRM metadata, Phase 3 intent signals, and Phase 4 technical website audits into channel-specific, evidence-backed outreach messages.

## Execution Flow
```text
Qualified Lead + Website Audit
              ↓
  Outreach Context Builder
              ↓
  Personalization & Pain Points
              ↓
  Channel Strategy & Constraints
              ↓
  Message Generator (3 Variants)
              ↓
  Evidence & Quality Validator
              ↓
  Human-in-the-Loop Approval Gate (READY_FOR_APPROVAL)
              ↓
  Reviewer Action (APPROVED / REJECTED)
```

## Security & Privacy
1. **Untrusted Data Isolation**: All prospect inputs, website text, and profile data are treated strictly as untrusted external text. Prompt injection attempts are neutralized and penalized.
2. **Deterministic Output Controls**: AI is strictly an interpretive assistant. Deterministic validators enforce length bounds, evidence mapping, and spam filters.
3. **Multi-Tenant Isolation**: All operations and database queries require valid tenant headers (`X-Organization-ID`).
