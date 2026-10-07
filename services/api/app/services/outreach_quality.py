import re
from typing import List, Tuple
from packages.shared_types.outreach import OutreachChannel
from services.api.app.agents.outreach.channel_strategy import ChannelLimits
from services.api.app.agents.outreach.outreach_models import (
    MessageValidationResult,
    OutreachContext,
)


class OutreachQualityScorer:
    """Calculates deterministic quality score (0-100) across 7 engineering dimensions."""

    SPAM_PATTERNS = [
        re.compile(r"guaranteed results", re.IGNORECASE),
        re.compile(r"act now", re.IGNORECASE),
        re.compile(r"limited time offer", re.IGNORECASE),
        re.compile(r"cheap prices", re.IGNORECASE),
        re.compile(r"leading it company in the world", re.IGNORECASE),
        re.compile(r"sir/madam", re.IGNORECASE),
    ]

    INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
        re.compile(r"send\s+(the\s+)?api\s*key", re.IGNORECASE),
        re.compile(r"system\s*:\s*", re.IGNORECASE),
    ]

    @classmethod
    def calculate_score(
        cls,
        body: str,
        context: OutreachContext,
        channel: OutreachChannel,
        evidence_coverage: float,
        validation_errors: List[str],
    ) -> Tuple[int, List[str], List[str]]:
        errors = list(validation_errors)
        warnings: List[str] = []

        # 1. Prompt Injection check
        for pat in cls.INJECTION_PATTERNS:
            if pat.search(body):
                errors.append("Hostile prompt injection sequence detected in draft.")
                return 0, errors, warnings

        # 2. Channel Length Bounds check
        min_len, max_len = ChannelLimits.get_bounds(channel)
        body_len = len(body.strip())
        if body_len < min_len:
            errors.append(f"Message length ({body_len}) is below channel minimum ({min_len}).")
        elif body_len > max_len:
            errors.append(f"Message length ({body_len}) exceeds channel maximum ({max_len}).")

        # 3. Spam and manipulation check
        for pat in cls.SPAM_PATTERNS:
            if pat.search(body):
                errors.append(f"Spammy/manipulative phrasing detected: '{pat.pattern}'")

        # Dimension 1: Evidence Coverage (max 25)
        # 0.0 -> 0, 1.0 -> 25
        cov_score = int(round(evidence_coverage * 25))

        # Dimension 2: Personalization (max 20)
        # Based on mention of company name, specific observation, or pain point
        pers_score = 5
        body_lower = body.lower()
        if context.company_name and context.company_name.lower() in body_lower:
            pers_score += 8
        if any(pp.statement.lower()[:20] in body_lower for pp in context.pain_points) or "mobile" in body_lower or "catalog" in body_lower or "store" in body_lower:
            pers_score += 7
        if context.contact_name and context.contact_name.lower() in body_lower:
            pers_score += 5
        pers_score = min(20, pers_score)

        # Dimension 3: Relevance (max 20)
        # Contextual alignment with lead's industry, signals, or website findings
        rel_score = 15
        if context.verified_signals or context.website_url or context.pain_points:
            rel_score = 20

        # Dimension 4: Service Alignment (max 15)
        # Mentions or reflects the recommended service category
        serv_score = 10
        rec_svc_words = context.recommended_service.lower().split("_")
        if any(w in body_lower for w in rec_svc_words if len(w) > 3):
            serv_score = 15

        # Dimension 5: Clarity (max 10)
        # Clean sentences, no excessive punctuation, appropriate line breaks
        clarity_score = 10
        if "???" in body or "!!!" in body:
            clarity_score -= 5
            warnings.append("Excessive punctuation detected.")

        # Dimension 6: CTA Quality (max 5)
        # Presence of polite/low-friction closing question
        cta_score = 5 if "?" in body else 2

        # Dimension 7: Natural Tone (max 5)
        tone_score = 5
        if "kindly" in body_lower or "dear sir" in body_lower:
            tone_score -= 3
            warnings.append("Stilted or archaic greeting used.")

        total_score = cov_score + pers_score + rel_score + serv_score + clarity_score + cta_score + tone_score

        # If hard errors exist, cap score strictly below 75
        if errors:
            total_score = min(total_score, 65)

        total_score = max(0, min(100, total_score))
        return total_score, errors, warnings
