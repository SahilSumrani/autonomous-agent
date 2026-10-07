import re
import time
from typing import Optional, Tuple
from packages.shared_types.conversation import IntentClassificationResult, ProspectIntent

# Precompiled regex patterns for deterministic classification
INTENT_PATTERNS = [
    # 1. SPAM_OR_BOT
    (
        re.compile(r"\b(?:crypto|forex|telegram|whatsapp\s+me|invest\s+with\s+us|earn\s+\$\d+|sugar\s+daddy|dm\s+me\s+on\s+telegram)\b", re.IGNORECASE),
        ProspectIntent.SPAM_OR_BOT,
        "Detected spam or promotional cryptocurrency/solicitation markers",
        0.98,
    ),
    # 2. NOT_INTERESTED
    (
        re.compile(r"\b(?:not\s+interested|unsubscribe|remove\s+me|please\s+stop|no\s+thanks|pass\s+on\s+this|don't\s+contact\s+me|leave\s+me\s+alone|do\s+not\s+message)\b", re.IGNORECASE),
        ProspectIntent.NOT_INTERESTED,
        "Explicit rejection or opt-out statement",
        0.95,
    ),
    # 3. MEETING_REQUEST
    (
        re.compile(r"\b(?:let's\s+(?:hop\s+on\s+a\s+)?call|schedule\s+a\s+(?:call|meeting|chat)|zoom|calendly|book\s+a\s+time|available\s+(?:tomorrow|this\s+week|next\s+week)|speak\s+on\s+the\s+phone)\b", re.IGNORECASE),
        ProspectIntent.MEETING_REQUEST,
        "Explicit request or availability to schedule a call/meeting",
        0.95,
    ),
    # 4. HIGH_INTEREST
    (
        re.compile(r"\b(?:ready\s+to\s+move\s+forward|definitely\s+interested|love\s+to\s+get\s+started|when\s+can\s+we\s+start|hire\s+you|let's\s+do\s+this|need\s+this\s+urgently)\b", re.IGNORECASE),
        ProspectIntent.HIGH_INTEREST,
        "High buying intent indicating eagerness to proceed",
        0.92,
    ),
    # 5. OBJECTION
    (
        re.compile(r"\b(?:too\s+expensive|price\s+is\s+too\s+high|no\s+budget|tight\s+budget|don't\s+need\s+a\s+website|bad\s+experience\s+with\s+agencies|can't\s+afford)\b", re.IGNORECASE),
        ProspectIntent.OBJECTION,
        "Commercial, financial, or skepticism objection voiced",
        0.94,
    ),
    # 6. PRICING_REQUEST
    (
        re.compile(r"\b(?:how\s+much\s+(?:does\s+it\s+cost|is\s+it)|what\s+(?:are\s+your\s+rates|is\s+the\s+price|is\s+the\s+cost)|pricing|rates|quote|rough\s+estimate|budget\s+required)\b", re.IGNORECASE),
        ProspectIntent.PRICING_REQUEST,
        "Inquiry regarding service pricing, cost, or fee estimates",
        0.93,
    ),
    # 7. PORTFOLIO_REQUEST
    (
        re.compile(r"\b(?:portfolio|examples\s+of\s+your\s+work|case\s+studies|past\s+projects|samples|links\s+to\s+(?:sites|stores)|show\s+me\s+what\s+you've\s+built)\b", re.IGNORECASE),
        ProspectIntent.PORTFOLIO_REQUEST,
        "Request for proof of work, case studies, or portfolio links",
        0.93,
    ),
    # 8. EXISTING_VENDOR
    (
        re.compile(r"\b(?:already\s+have\s+(?:an?\s+)?(?:developer|agency|team)|in-house\s+(?:team|devs|developer)|currently\s+working\s+with\s+someone|contracted\s+out|have\s+an?\s+agency)\b", re.IGNORECASE),
        ProspectIntent.EXISTING_VENDOR,
        "Prospect noted having an incumbent developer or agency partner",
        0.91,
    ),
    # 9. FOLLOW_UP_LATER
    (
        re.compile(r"\b(?:reach\s+out\s+(?:in\s+a\s+few\s+months|next\s+month|later|in\s+q[1-4])|circle\s+back\s+in|busy\s+right\s+now|bad\s+timing|not\s+right\s+now|revisit\s+later)\b", re.IGNORECASE),
        ProspectIntent.FOLLOW_UP_LATER,
        "Prospect requested follow-up at a future date",
        0.90,
    ),
    # 10. WRONG_PERSON
    (
        re.compile(r"\b(?:wrong\s+person|not\s+my\s+department|speak\s+with\s+our\s+(?:cto|founder|marketing)|i\s+don't\s+handle\s+this|reach\s+out\s+to\s+[\w@]+)\b", re.IGNORECASE),
        ProspectIntent.WRONG_PERSON,
        "Prospect indicated they are not the appropriate stakeholder",
        0.89,
    ),
    # 11. SERVICE_DETAILS
    (
        re.compile(r"\b(?:what\s+(?:technologies|stack|platform)|how\s+does\s+(?:it|the\s+process)\s+work|what\s+services\s+do\s+you\s+offer|shopify\s+or\s+custom|tell\s+me\s+more\s+about\s+what\s+you\s+do)\b", re.IGNORECASE),
        ProspectIntent.SERVICE_DETAILS,
        "Technical or process inquiry regarding TechVerse capabilities",
        0.86,
    ),
    # 12. INTERESTED
    (
        re.compile(r"\b(?:interested|sounds\s+(?:good|interesting|cool)|tell\s+me\s+more|send\s+more\s+info|curious|open\s+to\s+hearing\s+more|what\s+do\s+you\s+have\s+in\s+mind)\b", re.IGNORECASE),
        ProspectIntent.INTERESTED,
        "Positive reception and openness to exploring options",
        0.85,
    ),
    # 13. OUT_OF_SCOPE
    (
        re.compile(r"\b(?:only\s+need\s+(?:seo|social\s+media|content|native\s+ios|swift)|social\s+media\s+management\s+only|content\s+writing\s+only|native\s+ios\s+swift|swift\s+app\s+only)\b", re.IGNORECASE),
        ProspectIntent.OUT_OF_SCOPE,
        "Inquiry strictly requests services outside TechVerse core agency offerings",
        0.82,
    ),
    # 14. QUESTION
    (
        re.compile(r"\b(?:can\s+you|do\s+you|is\s+it\s+possible|how\s+long\s+does\s+it\s+take|\?)\b", re.IGNORECASE),
        ProspectIntent.QUESTION,
        "General inquiry or question awaiting clarification",
        0.75,
    ),
]


class IntentClassifier:
    """
    Deterministic intent classification engine with fallback handling.
    Accurately categorizes inbound messages into 16 standardized ProspectIntent classes.
    """

    @classmethod
    def classify(cls, text: str) -> IntentClassificationResult:
        cleaned = text.strip()
        if not cleaned:
            return IntentClassificationResult(
                intent=ProspectIntent.UNKNOWN,
                confidence=0.5,
                evidence="Empty or whitespace-only message",
                reasoning="No semantic tokens detected",
                created_at=time.time(),
            )

        # Iterate over deterministic rule patterns in priority order
        for pattern, intent, reasoning, conf in INTENT_PATTERNS:
            match = pattern.search(cleaned)
            if match:
                evidence = match.group(0)
                return IntentClassificationResult(
                    intent=intent,
                    confidence=conf,
                    evidence=evidence,
                    reasoning=reasoning,
                    created_at=time.time(),
                )

        # Ambiguous short messages
        if len(cleaned.split()) <= 2:
            return IntentClassificationResult(
                intent=ProspectIntent.NEEDS_CLARIFICATION,
                confidence=0.65,
                evidence=cleaned[:100],
                reasoning="Message is too short to determine intent unambiguously",
                created_at=time.time(),
            )

        # Default fallback
        return IntentClassificationResult(
            intent=ProspectIntent.UNKNOWN,
            confidence=0.50,
            evidence=cleaned[:100],
            reasoning="No specific intent markers or objection keywords identified",
            created_at=time.time(),
        )
