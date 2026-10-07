import re
from typing import List, Optional
from pydantic import BaseModel, Field


class OpportunityEvaluation(BaseModel):
    """Structured evaluation returned by the opportunity detection engine."""
    is_opportunity: bool = False
    opportunity_type: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: List[str] = Field(default_factory=list)
    recommended_service: Optional[str] = None
    detected_intent: Optional[str] = None
    business_category: Optional[str] = None


# Intent rules mapping patterns to signals, confidence, and recommended TechVerse services
INTENT_PATTERNS = [
    {
        "pattern": r"\b(need|looking for|want|hire|seeking)\s+(a\s+)?(website|web site|web developer|web designer)\b",
        "type": "WEBSITE_REQUEST",
        "service": "Business Website",
        "confidence": 0.95,
        "intent": "Seeking web development partner",
    },
    {
        "pattern": r"\b(website\s+redesign|redesign\s+my\s+website|new\s+website|rebuild\s+(my\s+)?website)\b",
        "type": "WEBSITE_REDESIGN",
        "service": "Website Redesign",
        "confidence": 0.92,
        "intent": "Looking to revamp outdated digital presence",
    },
    {
        "pattern": r"\b(need|looking for|build|develop)\s+(an?\s+)?(app|mobile app|ios app|android app)\b",
        "type": "APP_DEVELOPMENT_REQUEST",
        "service": "Mobile App",
        "confidence": 0.94,
        "intent": "Mobile application development required",
    },
    {
        "pattern": r"\b(ai\s+automation|automate\s+(my|our)\s+business|ai\s+agents?|custom\s+ai)\b",
        "type": "AI_AUTOMATION_REQUEST",
        "service": "AI Automation",
        "confidence": 0.93,
        "intent": "Operational AI workflow automation interest",
    },
    {
        "pattern": r"\b(launching|starting|opening)\s+(a|my|our)?\s*([a-z]+\s+)*(clothing|brand|store|ecommerce|business|startup|shop|boutique)\b",
        "type": "BUSINESS_LAUNCH",
        "service": "E-commerce Website",
        "confidence": 0.88,
        "intent": "New venture launch requiring digital storefront",
    },
    {
        "pattern": r"\b(figure out|set up|need|build|looking for)\s+(an?\s+)?([a-z]+\s+)*(online store|ecommerce|shopify|checkout|storefront)\b",
        "type": "ECOMMERCE_OPPORTUNITY",
        "service": "E-commerce Website",
        "confidence": 0.90,
        "intent": "E-commerce infrastructure setup needed",
    },
    {
        "pattern": r"\b(looking for\s+(an?\s+)?agency|hire\s+an?\s+agency|need\s+an?\s+agency)\b",
        "type": "AGENCY_SEARCH",
        "service": "Premium Website",
        "confidence": 0.91,
        "intent": "Agency partnership search",
    },
    {
        "pattern": r"\b(my\s+website\s+(sucks|is broken|is slow|doesn't convert)|can't get sales on website)\b",
        "type": "POOR_CONVERSION",
        "service": "Performance Optimization",
        "confidence": 0.89,
        "intent": "Pain point with existing site performance or conversion",
    },
]


class OpportunityDetector:
    """Deterministic and semantic opportunity detector for public web content."""

    @classmethod
    def evaluate_content(
        cls,
        text: Optional[str],
        profile_bio: Optional[str] = None,
        website_text: Optional[str] = None,
    ) -> OpportunityEvaluation:
        """
        Evaluate visible text, bio, or website content for high-intent business opportunities.
        Deterministic regex heuristic with confidence scoring.
        """
        combined = f"{text or ''} {profile_bio or ''} {website_text or ''}".strip().lower()
        if not combined:
            return OpportunityEvaluation(is_opportunity=False)

        best_match = None
        highest_conf = 0.0
        evidence_list = []

        for rule in INTENT_PATTERNS:
            matches = re.finditer(rule["pattern"], combined, re.IGNORECASE)
            for m in matches:
                matched_snippet = m.group(0)
                evidence_text = f"Detected buying signal pattern: '{matched_snippet}' in content context."
                evidence_list.append(evidence_text)
                if rule["confidence"] > highest_conf:
                    highest_conf = rule["confidence"]
                    best_match = rule

        if best_match:
            return OpportunityEvaluation(
                is_opportunity=True,
                opportunity_type=best_match["type"],
                confidence=highest_conf,
                evidence=evidence_list,
                recommended_service=best_match["service"],
                detected_intent=best_match["intent"],
            )

        return OpportunityEvaluation(
            is_opportunity=False,
            confidence=0.1,
            evidence=["No verified buying signal or service need detected in public text."],
        )
