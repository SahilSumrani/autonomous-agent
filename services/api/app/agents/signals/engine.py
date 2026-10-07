import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from packages.shared_types.crm import SignalType


class DetectedSignal(BaseModel):
    """Normalized detected buying or need signal."""
    signal_type: SignalType
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: str
    source_url: Optional[str] = None
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# False positive indicator patterns (e.g. competitors, job seekers, casual consumers)
DISQUALIFYING_PATTERNS = [
    r"\b(i am|i'm|as a)\s+(a\s+)?(web developer|web designer|freelance developer|software engineer)\s+(looking for|seeking|available for)\s+(clients|work|projects)\b",
    r"\b(hire me|my portfolio|check out my portfolio|freelancer available)\b",
    r"\b(anyone know a good website (to|for|where|that))\s+(watch|stream|play|download|read|buy shoes)\b",
    r"\b(i built|we already built|just launched|finished building)\s+(my|our|a)\s+(website|app)\b",
]
DISQUALIFYING_REGEX = re.compile("|".join(DISQUALIFYING_PATTERNS), re.IGNORECASE)


# Rules for all 18 signal types
SIGNAL_TAXONOMY_RULES: List[Dict[str, Any]] = [
    {
        "type": SignalType.WEBSITE_REQUEST,
        "pattern": r"\b(need|looking for|want|hire|seeking)\s+(an?\s+)?(new\s+)?(website|web site|landing page|web developer|web designer|web dev)\b|\b(looking for\s+)?someone to build\s+(an?\s+)?(new\s+)?(website|site|landing page|web\s*app)\b|\b(build|develop|redesign)\s+(me|us|our|a)?\s*(new\s+)?(website|site|landing page)\b",
        "confidence": 0.95,
        "template": "Explicit public request seeking a website or web developer.",
    },
    {
        "type": SignalType.WEBSITE_OUTDATED,
        "pattern": r"\b(redesign(ing)?|revamp(ing)?|rebuild(ing)?|re-design|our\s+site\s+looks\s+(old|ancient|dated|90s)|haven't\s+updated\s+our\s+website\s+in\s+years)\b",
        "confidence": 0.92,
        "template": "Evidence of outdated design or explicit need for website redesign.",
    },
    {
        "type": SignalType.APP_DEVELOPMENT_REQUEST,
        "pattern": r"\b(need|looking for|build|develop)\s+(an?\s+)?(mobile app|ios app|android app|react native app|flutter app)\b",
        "confidence": 0.94,
        "template": "Request identified for custom mobile application development.",
    },
    {
        "type": SignalType.AI_AUTOMATION_REQUEST,
        "pattern": r"\b(ai\s+automation|automate\s+(my|our)\s+workflows?|ai\s+agents?|custom\s+llm|ai\s+bot|automation\s+agency)\b",
        "confidence": 0.93,
        "template": "Business seeking AI automation or agentic workflow development.",
    },
    {
        "type": SignalType.HIRING_DEVELOPER,
        "pattern": r"\b(hiring|looking to hire|we're hiring)\s+(a\s+)?(developer|frontend|backend|fullstack|software engineer|tech lead)\b",
        "confidence": 0.90,
        "template": "Active hiring posting for software or web development talent.",
    },
    {
        "type": SignalType.HIRING_DESIGNER,
        "pattern": r"\b(hiring|looking to hire|we're hiring)\s+(a\s+)?(ui\/?ux designer|product designer|web designer|graphic designer)\b",
        "confidence": 0.88,
        "template": "Active hiring posting for UI/UX or digital product design.",
    },
    {
        "type": SignalType.BUSINESS_LAUNCH,
        "pattern": r"\b(launching|opening|starting)\s+(my|our|a)?\s*([a-z]+\s+)*(clothing|brand|store|startup|business|company|agency|boutique|studio)\b|\b(launching|launch)\s+(next month|soon|this month|next week)\b",
        "confidence": 0.89,
        "template": "Commercial announcement regarding new business or brand launch.",
    },
    {
        "type": SignalType.NEW_PRODUCT,
        "pattern": r"\b(launching|announcing|releasing)\s+(our|a)?\s*(new product|flagship product|v2|new line|new collection)\b",
        "confidence": 0.85,
        "template": "Product release announcement requiring marketing & digital presence.",
    },
    {
        "type": SignalType.BUSINESS_EXPANSION,
        "pattern": r"\b(expanding|expansion|opened\s+our\s+second|new\s+location|scaling\s+operations|entering\s+new\s+market)\b",
        "confidence": 0.86,
        "template": "Business expansion indicating increased scale and capital.",
    },
    {
        "type": SignalType.GROWTH_SIGNAL,
        "pattern": r"\b(doubled\s+our\s+revenue|10x\s+growth|scaling\s+fast|hit\s+(10k|100k|1m)\s+in\s+sales|high\s+demand)\b",
        "confidence": 0.85,
        "template": "Public growth indicators and strong commercial traction.",
    },
    {
        "type": SignalType.RECENT_FUNDING,
        "pattern": r"\b(raised|secured|closed)\s+(\$\d+m?|\d+k|seed\s+round|series\s+a|funding\s+round|pre-seed)\b",
        "confidence": 0.96,
        "template": "Verified venture funding or capital raise announcement.",
    },
    {
        "type": SignalType.ECOMMERCE_OPPORTUNITY,
        "pattern": r"\b(need|set up|figuring out|looking for)\s+(an?\s+)?(online store|ecommerce|shopify|woocommerce|cart|checkout)\b",
        "confidence": 0.91,
        "template": "Intent to deploy or upgrade an online e-commerce storefront.",
    },
    {
        "type": SignalType.REQUEST_FOR_SERVICE,
        "pattern": r"\b(recommend|looking for|seeking)\s+(an?\s+)?(agency|consultant|service provider|technical partner|dev shop)\b",
        "confidence": 0.89,
        "template": "Public request for specialized agency or technical service partner.",
    },
    {
        "type": SignalType.WEBSITE_SLOW,
        "pattern": r"\b(website\s+is\s+(so\s+)?slow|loading\s+takes\s+forever|speed\s+issues\s+on\s+(my|our)\s+site)\b",
        "confidence": 0.88,
        "template": "Reported or observed site latency and page load bottlenecks.",
    },
    {
        "type": SignalType.POOR_MOBILE_UX,
        "pattern": r"\b(mobile\s+version\s+is\s+(broken|unusable|bad)|looks\s+terrible\s+on\s+phones?|not\s+mobile\s+friendly)\b",
        "confidence": 0.90,
        "template": "Deficiencies identified in mobile responsiveness and viewport UX.",
    },
    {
        "type": SignalType.WEAK_CONVERSION,
        "pattern": r"\b(visitors\s+aren't\s+converting|zero\s+sales\s+from\s+traffic|high\s+bounce\s+rate|checkout\s+drop-off)\b",
        "confidence": 0.89,
        "template": "Conversion rate optimization challenge on current digital channel.",
    },
    {
        "type": SignalType.WEAK_SEO,
        "pattern": r"\b(can't\s+rank\s+on\s+google|no\s+organic\s+traffic|terrible\s+seo|need\s+seo\s+help)\b",
        "confidence": 0.86,
        "template": "Search engine visibility and indexing weakness reported.",
    },
    {
        "type": SignalType.TECH_STACK_CHANGE,
        "pattern": r"\b(migrating\s+from\s+wordpress|switching\s+to\s+nextjs|moving\s+off\s+wix|re-platforming|replacing\s+legacy\s+stack)\b",
        "confidence": 0.91,
        "template": "Active re-platforming or technical stack migration.",
    },
]


class SignalDetectionEngine:
    """Hybrid deterministic & semantic signal engine with anti-false-positive filtering."""

    @classmethod
    def sanitize_text(cls, raw: Optional[str]) -> str:
        """Sanitize input text and treat potential prompt injections strictly as inert data."""
        if not raw:
            return ""
        # Strip null bytes and normalize whitespace
        cleaned = raw.replace("\x00", " ").strip()
        return cleaned

    @classmethod
    def check_false_positive(cls, text: str) -> bool:
        """Return True if text represents a competitor, job seeker, or non-buyer query."""
        return bool(DISQUALIFYING_REGEX.search(text))

    @classmethod
    def detect_signals(
        cls,
        text: Optional[str],
        source_url: Optional[str] = None,
        profile_bio: Optional[str] = None,
        website_text: Optional[str] = None,
    ) -> List[DetectedSignal]:
        """
        Detect signals from visible page, bio, and website context.
        Applies false positive filtering and regex taxonomy matching.
        """
        combined = " ".join(filter(None, [
            cls.sanitize_text(text),
            cls.sanitize_text(profile_bio),
            cls.sanitize_text(website_text),
        ])).strip()

        if not combined:
            return []

        # Anti-false-positive filter: Reject competitor/job-seeker profiles
        if cls.check_false_positive(combined):
            return []

        signals: List[DetectedSignal] = []
        seen_types = set()

        for rule in SIGNAL_TAXONOMY_RULES:
            match = re.search(rule["pattern"], combined, re.IGNORECASE)
            if match and rule["type"] not in seen_types:
                matched_text = match.group(0)
                evidence = f"{rule['template']} Matched phrase: '{matched_text}'."
                signals.append(
                    DetectedSignal(
                        signal_type=rule["type"],
                        confidence=rule["confidence"],
                        evidence=evidence,
                        source_url=source_url,
                    )
                )
                seen_types.add(rule["type"])

        return signals

    analyze = detect_signals

