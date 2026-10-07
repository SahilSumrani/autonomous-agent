# Conversation Intelligence Security & Trust Controls

## 1. Threat Model & Trust Boundary
All inbound prospect messages originate from untrusted external sources and represent unauthenticated external input.
Threats addressed:
1. **Prompt Injection & System Prompt Leakage**: Attackers asking the agent to ignore previous instructions, output internal instructions, or leak API keys.
2. **Autonomous Commercial Exposure**: The AI agreeing to discounts, binding contract terms, impossible deadlines, or non-existent warranties.
3. **Wrong Context / Recipient Transmission**: Sending responses to the wrong thread or mismatching recipient handles.
4. **Tenant Isolation Breach**: Cross-tenant thread or reply inspection.

## 2. Inbound Sanitization Engine
- Replaces prompt injection patterns (`ignore all instructions`, `reveal api key`, `system prompt`) with `[FILTERED_INPUT]`.
- Strips executable HTML/JavaScript tags and template injection symbols (`{{...}}`).
- Imposes strict 4,000 character maximum payload truncation on inbound messages.

## 3. Human Approval Policy
- Autonomous external message sending is strictly forbidden.
- Reply candidates must score >= 75 and contain zero prohibited commitments.
- The `/send` API endpoint strictly validates that `ConversationApproval` exists with status `APPROVED`.

## 4. Wrong Context & Delivery Uncertainty Defense
- The browser dispatch pipeline checks `organization_id`, `lead_id`, `thread_id`, and expected recipient handle against active browser tab context.
- If delivery state cannot be deterministically verified, status is set to `DELIVERY_UNKNOWN`, and the operation is halted for human review rather than retried.
