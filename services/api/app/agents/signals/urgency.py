import re
from enum import Enum
from typing import Optional, Tuple
from pydantic import BaseModel, Field


class UrgencyLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"


class UrgencyResult(BaseModel):
    level: UrgencyLevel
    score: int = Field(..., ge=0, le=100)
    reason: str
    evidence: Optional[str] = None


# Deterministic pattern matchers for strictly observed urgency evidence
CRITICAL_PATTERNS = [
    (r"\b(asap|urgently|emergency|need\s+today|within\s+24\s+hours|within\s+48\s+hours|need\s+right\s+now|immediate(ly)?\s+need|launching\s+in\s+[1-5]\s+days)\b", "Immediate or critical turnaround required ('{match}')."),
    (r"\b(need\s+a\s+developer\s+urgently|looking\s+for\s+someone\s+immediately)\b", "Explicit urgent developer/service requirement ('{match}')."),
]

HIGH_PATTERNS = [
    (r"\b(need\s+this\s+week|this\s+week|by\s+friday|by\s+end\s+of\s+week)\b", "Requirement due this week ('{match}')."),
    (r"\b(launching\s+next\s+week|launch\s+is\s+next\s+week|launching\s+in\s+([1-9]|1[0-4])\s+days|launch\s+is\s+in\s+([1-9]|1[0-4])\s+days)\b", "Imminent product/startup launch within days ('{match}')."),
    (r"\b(launching\s+this\s+month|launching\s+next\s+month|launching\s+soon|launch\s+soon)\b", "Product launch scheduled in near term ('{match}')."),
    (r"\b(need\s+website\s+before\s+launch|need\s+site\s+before\s+launch|before\s+(we\s+)?launch)\b", "Website/system required prior to impending launch ('{match}')."),
    (r"\b(ready\s+to\s+start\s+immediately|ready\s+to\s+hire\s+today|ready\s+to\s+hire\s+now|budget\s+ready|funded\s+and\s+ready)\b", "Commercial client ready to start immediately ('{match}')."),
    (r"\b(looking\s+to\s+start\s+(asap|this\s+week|now))\b", "Immediate engagement start timeline ('{match}')."),
]

MEDIUM_PATTERNS = [
    (r"\b(next\s+month|looking\s+to\s+start\s+next\s+month|in\s+a\s+few\s+weeks|planning\s+for\s+q[1-4]|planning\s+for\s+next\s+quarter)\b", "Planned project kickoff within 1-3 months ('{match}')."),
    (r"\b(starting\s+soon|in\s+the\s+coming\s+weeks|pre-launch|building\s+mvp\s+for\s+summer)\b", "Near-term development timeframe ('{match}')."),
]

LOW_PATTERNS = [
    (r"\b(eventually|someday|in\s+the\s+future|exploring\s+ideas|thinking\s+about\s+(building|redesigning)|down\s+the\s+road)\b", "Exploratory inquiry without immediate timeline ('{match}')."),
    (r"\b(no\s+rush|no\s+strict\s+deadline|flexible\s+timeline)\b", "Flexible or long-term timeline ('{match}')."),
]


class UrgencyDetector:
    """
    Deterministic, evidence-grounded urgency classifier for observed prospect communications.
    Strictly forbids inferring urgency purely because a subject is a startup.
    Every non-NONE urgency decision is backed by observable textual phrases.
    """

    @classmethod
    def evaluate(cls, text: Optional[str]) -> UrgencyResult:
        if not text:
            return UrgencyResult(
                level=UrgencyLevel.NONE,
                score=10,
                reason="No temporal indicators or urgency language observed.",
                evidence=None,
            )

        clean_text = text.replace("\x00", " ").strip()

        # 1. Check CRITICAL
        for pat, reason_tmpl in CRITICAL_PATTERNS:
            m = re.search(pat, clean_text, re.IGNORECASE)
            if m:
                matched_phrase = m.group(0)
                reason = reason_tmpl.format(match=matched_phrase)
                return UrgencyResult(
                    level=UrgencyLevel.CRITICAL,
                    score=95,
                    reason=f"Post exhibits critical urgency: {reason}",
                    evidence=matched_phrase,
                )

        # 2. Check HIGH
        for pat, reason_tmpl in HIGH_PATTERNS:
            m = re.search(pat, clean_text, re.IGNORECASE)
            if m:
                matched_phrase = m.group(0)
                reason = reason_tmpl.format(match=matched_phrase)
                return UrgencyResult(
                    level=UrgencyLevel.HIGH,
                    score=85,
                    reason=f"Post exhibits high urgency: {reason}",
                    evidence=matched_phrase,
                )

        # 3. Check MEDIUM
        for pat, reason_tmpl in MEDIUM_PATTERNS:
            m = re.search(pat, clean_text, re.IGNORECASE)
            if m:
                matched_phrase = m.group(0)
                reason = reason_tmpl.format(match=matched_phrase)
                return UrgencyResult(
                    level=UrgencyLevel.MEDIUM,
                    score=60,
                    reason=f"Post exhibits medium urgency: {reason}",
                    evidence=matched_phrase,
                )

        # 4. Check LOW
        for pat, reason_tmpl in LOW_PATTERNS:
            m = re.search(pat, clean_text, re.IGNORECASE)
            if m:
                matched_phrase = m.group(0)
                reason = reason_tmpl.format(match=matched_phrase)
                return UrgencyResult(
                    level=UrgencyLevel.LOW,
                    score=35,
                    reason=f"Post exhibits low urgency: {reason}",
                    evidence=matched_phrase,
                )

        # 5. Default NONE
        return UrgencyResult(
            level=UrgencyLevel.NONE,
            score=15,
            reason="No explicit deadline or urgency phrase observed in content.",
            evidence=None,
        )
