import re
from typing import Optional
from packages.shared_types.conversation import ObjectionClassification

OBJECTION_RULES = [
    (
        re.compile(r"\b(?:too\s+expensive|rates\s+are\s+high|price\s+is\s+too\s+high|can't\s+afford|too\s+pricey)\b", re.IGNORECASE),
        "PRICE_TOO_HIGH",
        "HIGH",
        "Acknowledge pricing sensitivity. Clarify modular scope options and milestone pricing. Emphasize focused deliverables over all-or-nothing rebuilds.",
        [
            "Do NOT offer automatic discounts or price cuts.",
            "Do NOT invent arbitrary ROI metrics or revenue numbers.",
            "Do NOT make price commitments without human approval.",
        ],
    ),
    (
        re.compile(r"\b(?:no\s+budget|don't\s+have\s+the\s+budget|tight\s+budget|funds\s+are\s+limited)\b", re.IGNORECASE),
        "NO_BUDGET",
        "MEDIUM",
        "Acknowledge budget constraints gracefully. Offer to share a free technical audit roadmap or follow up when resources become available.",
        [
            "Do NOT pressure the prospect.",
            "Do NOT offer pro-bono work or unsanctioned free builds.",
        ],
    ),
    (
        re.compile(r"\b(?:already\s+have\s+(?:a\s+)?(?:developer|agency)|in-house\s+team|current\s+agency|working\s+with\s+someone)\b", re.IGNORECASE),
        "INCUMBENT_AGENCY_OR_DEV",
        "MEDIUM",
        "Respect existing relationships. Offer specialized ad-hoc support, performance audits, or keep the door open for future overflow requirements.",
        [
            "Do NOT criticize or disparage their current agency or developers.",
            "Do NOT attempt aggressive displacement tactics.",
        ],
    ),
    (
        re.compile(r"\b(?:bad\s+experience|burned\s+by\s+agencies|skeptical|don't\s+trust\s+agencies)\b", re.IGNORECASE),
        "SKEPTICISM_BAD_EXPERIENCE",
        "HIGH",
        "Validate their frustration. Emphasize transparent milestone-based deliverables, full code ownership, and zero lock-in agreements.",
        [
            "Do NOT make defensive statements.",
            "Do NOT guarantee flawless outcomes.",
        ],
    ),
    (
        re.compile(r"\b(?:maybe\s+later|busy\s+right\s+now|revisit\s+(?:next\s+month|in\s+q[1-4])|bad\s+timing)\b", re.IGNORECASE),
        "BAD_TIMING",
        "LOW",
        "Respect timing priorities. Confirm a specific future date to reconnect without frequent follow-up badgering.",
        [
            "Do NOT push for immediate action when the prospect explicitly requested a delay.",
        ],
    ),
]


class ObjectionHandler:
    """
    Analyzes prospect statements for objections and produces consultative strategy guardrails.
    """

    @classmethod
    def evaluate(cls, text: str) -> Optional[ObjectionClassification]:
        cleaned = text.strip()
        for pattern, obj_type, severity, strategy, do_not_claim in OBJECTION_RULES:
            if pattern.search(cleaned):
                return ObjectionClassification(
                    objection_type=obj_type,
                    severity=severity,
                    recommended_strategy=strategy,
                    do_not_claim=do_not_claim,
                    requires_human_approval=True,
                )
        return None
