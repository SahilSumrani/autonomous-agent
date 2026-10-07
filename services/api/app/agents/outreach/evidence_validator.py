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

        # If body mentions Shopify or specific tech, verify tech in context
        if "shopify" in body_lower:
            cms_detected = context.website_findings.get("cms") or context.website_findings.get("ecommerce_platform")
            if not cms_detected or "shopify" not in str(cms_detected).lower():
                # Check signals
                has_sig = any("shopify" in str(s).lower() for s in context.verified_signals)
                if not has_sig:
                    warnings.append("Mentioned Shopify without verified technical evidence.")

        # 3. Calculate evidence coverage
        evidence_points = len(context.evidence)
        if evidence_points == 0:
            coverage = 0.5  # Only basic CRM context
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
