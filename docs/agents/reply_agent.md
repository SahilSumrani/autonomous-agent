# Reply Agent & Reply Strategy Engine

## 1. Overview
The **Reply Agent** formulates structured, consultative responses to inbound prospect communications. It ensures every draft is personalized, evidence-backed, grounded in discovered technical findings, bounded by strict channel length limits, and completely free of fabricated claims.

## 2. Reply Generation Philosophy
- **No Hallucinations**: Never invent client testimonials, past metrics, revenue claims, or capabilities.
- **Strict Channel Character Constraints**:
  - `INSTAGRAM_DM`: 50 – 700 characters
  - `REDDIT`: 80 – 1200 characters
  - `LINKEDIN`: 100 – 1000 characters
  - `EMAIL`: 100 – 2000 characters
- **Prohibited Commitments**:
  - Autonomous discounts or free trial offers
  - Guarantees of ROI, ranking, or revenue
  - Contract signing or legal commitments
  - Binding fixed pricing commitments
  - Autonomous refund policies

## 3. Reply Variants
The Reply Agent generates up to 3 distinct response variants:
1. **DIRECT**: Concise, transparent, and straight to the point.
2. **CONVERSATIONAL**: Warm, consultative, and relationship-oriented.
3. **INSIGHT_LED**: Value-first, citing specific website/technology findings discovered during Phase 4 research.

## 4. Deterministic Quality Validation
Before any reply draft can enter the approval queue, it is evaluated across 8 quality dimensions (Relevance, Personalization, Evidence Grounding, Clarity, Helpfulness, Channel Fit, CTA Quality, Safety):
- Minimum score required: **75 / 100**
- Any prohibited commitment instantly triggers rejection (`NEEDS_REGENERATION`).
- If compliant and >= 75: Draft marked as `READY_FOR_APPROVAL`.

## 5. Human Approval Gate
External messaging is strictly gated. A human operator must review and approve the draft before browser dispatch can occur:
```text
DRAFT → VALIDATED (>=75) → READY_FOR_APPROVAL → Human Approves → APPROVED → Dispatch
```
