import re
from typing import List, Set, Tuple
from services.api.app.agents.outreach.outreach_models import (
    OutreachContext,
    OutreachEvidenceModel,
)


class EvidenceValidator:
    """Validates that outreach claims strictly map to confirmed context and rejects hallucinations."""

    HALLUCINATION_PATTERNS = [
        re.compile(r"following you for months", re.IGNORECASE),
        re.compile(r"following your company for (years|months)", re.IGNORECASE),
        re.compile(r"huge fan of your", re.IGNORECASE),
        re.compile(r"recent (series [a-z]|funding round|\$\d+m)", re.IGNORECASE),
        re.compile(r"guarantee \d+%", re.IGNORECASE),
        re.compile(r"increase your (sales|revenue) by \d+%", re.IGNORECASE),
        re.compile(r"noticed your sales are (suffering|dropping|down)", re.IGNORECASE),
        re.compile(r"we worked with your competitor", re.IGNORECASE),
        re.compile(r"mutual friend", re.IGNORECASE),
    ]

    @classmethod
    def validate_evidence_alignment(
        cls,
        body: str,
        context: OutreachContext,
    ) -> Tuple[bool, List[str], List[str], float]:
        errors: List[str] = []
        warnings: List[str] = []
        unsupported_claims: List[str] = []

        # 1. Check for blatant hallucinated relationship / metric tropes
        for pat in cls.HALLUCINATION_PATTERNS:
            match = pat.search(body)
            if match:
                errors.append(f"Unsubstantiated claim or hallucination detected: '{match.group(0)}'")
                unsupported_claims.append(match.group(0))

        # 2. Check if specific claims match context
        body_lower = body.lower()

        # If body mentions specific technologies, verify tech in context
        for tech in ["shopify", "wordpress", "magento", "woocommerce", "webflow"]:
            if tech in body_lower:
                cms_detected = context.website_findings.get("cms") or context.website_findings.get("ecommerce_platform")
                has_tech = (cms_detected and tech in str(cms_detected).lower()) or any(
                    tech in str(s).lower() for s in context.verified_signals
                ) or any(
                    tech in ev.claim.lower() for ev in context.evidence
                )
                if not has_tech:
                    errors.append(f"Mentioned {tech.capitalize()} without verified technical evidence.")
                    unsupported_claims.append(tech)

        # 3. Check for ungrounded technical problem assertions
        technical_flaw_patterns = [
            (re.compile(r"(friction point|checkout drop-off|drop-off)", re.IGNORECASE), "friction or drop-off"),
            (re.compile(r"recently launched .* store", re.IGNORECASE), "recent store launch"),
            (re.compile(r"(slow|load speed|performance bottleneck)", re.IGNORECASE), "site speed/performance"),
            (re.compile(r"(poor mobile|mobile rendering|viewport)", re.IGNORECASE), "mobile rendering"),
            (re.compile(r"(lacks? cta|no call-to-action|missing cta)", re.IGNORECASE), "call-to-action issues"),
            (re.compile(r"(seo problem|missing meta|poor search)", re.IGNORECASE), "SEO weaknesses"),
        ]

        for regex, flaw_name in technical_flaw_patterns:
            if regex.search(body):
                # Verify that this flaw exists in context.evidence or pain_points or verified_signals
                has_flaw_evidence = any(
                    regex.search(ev.claim) or regex.search(ev.evidence_text)
                    for ev in context.evidence
                ) or any(
                    regex.search(p.statement)
                    for p in context.pain_points
                ) or any(
                    flaw_name.lower() in str(s).lower()
                    for s in context.verified_signals
                )
                if not has_flaw_evidence:
                    errors.append(f"Claimed unverified technical flaw ({flaw_name}) without supporting evidence.")
                    unsupported_claims.append(flaw_name)

        # 4. Calculate evidence coverage
        evidence_points = len(context.evidence)
        if evidence_points == 0:
            if len(errors) > 0:
                coverage = 0.0
            else:
                coverage = 0.8  # Clean non-factual introduction based only on verified entity context
        else:
            # Check how many evidence claims are reflected in the text
            matched_evidence = 0
            for ev in context.evidence:
                words = [w.lower() for w in re.findall(r"\w{4,}", ev.claim) if w.lower() not in {"detected", "observed", "website", "signal"}]
                if any(w in body_lower for w in words):
                    matched_evidence += 1
            coverage = min(1.0, max(0.4, matched_evidence / max(1, min(3, evidence_points))))

        valid = len(errors) == 0
        return valid, errors, warnings, coverage
