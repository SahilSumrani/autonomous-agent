# Conversation Intelligence Engine

## 1. Overview
The **Conversation Intelligence Engine** continues the prospect client acquisition lifecycle immediately after an approved Phase 5 outreach message is dispatched and the prospect replies back across supported channels (`INSTAGRAM_DM`, `REDDIT`, `LINKEDIN`, `EMAIL`).

The engine receives untrusted inbound prospect communications, defangs malicious prompt injections, deterministically classifies intent into 16 standardized taxonomy categories, tracks objections, synthesizes rolling conversation context, and transitions sales pipeline stages safely.

## 2. Inbound Processing Architecture

```text
Inbound Prospect Message
        ↓
Prompt Injection Sanitization & Content Isolation
        ↓
Message Idempotency Check (external_message_ref / hash-window)
        ↓
Intent Classification (16 Classes, deterministic regex + semantic fallback)
        ↓
Objection Analysis & Guidance Formulation
        ↓
Rolling Memory & Context Synthesis
        ↓
Deterministic Sales Stage State Machine
        ↓
Reply Strategy Engine
        ↓
Reply Generation (DIRECT, CONVERSATIONAL, INSIGHT_LED)
        ↓
Quality & Veracity Validation (Score >= 75)
        ↓
Human Approval Gate (HUMAN_REQUIRED)
        ↓
Phase 6 Chrome Browser Gateway Execution
```

## 3. Supported Intent Categories (16 Classes)
1. `INTERESTED`: General positive reception and curiosity.
2. `HIGH_INTEREST`: Immediate eagerness, buying signal, ready to move forward.
3. `PRICING_REQUEST`: Inquiry about cost, fees, rates, or budget expectations.
4. `PORTFOLIO_REQUEST`: Asks for case studies, examples, past work.
5. `SERVICE_DETAILS`: Technical inquiry about capabilities, tech stack, deliverables.
6. `MEETING_REQUEST`: Request or availability to book a Zoom, Calendly, or phone call.
7. `NOT_INTERESTED`: Explicit opt-out or rejection.
8. `FOLLOW_UP_LATER`: Timing objection, revisit next month or Q4.
9. `EXISTING_VENDOR`: Incumbent developer or agency partner in place.
10. `WRONG_PERSON`: Indicated they are not the appropriate stakeholder.
11. `OBJECTION`: Commercial resistance (price too high, no budget, skepticism).
12. `QUESTION`: General clarifying inquiry.
13. `NEEDS_CLARIFICATION`: Ambiguous reply requiring further questions.
14. `SPAM_OR_BOT`: Promotional spam, phishing, or bot traffic.
15. `OUT_OF_SCOPE`: Inquiry strictly outside core agency capabilities.
16. `UNKNOWN`: Unclassifiable noise.

## 4. Safety & Trust Boundaries
- **Untrusted Input**: All inbound prospect text is treated as hostile by default. Prompt injection markers (`ignore all instructions`, `reveal api key`, `<script>`) are sanitized prior to processing.
- **Zero Autonomous Commitments**: Intent classifications never trigger autonomous discounts, pricing guarantees, or legal agreements.
