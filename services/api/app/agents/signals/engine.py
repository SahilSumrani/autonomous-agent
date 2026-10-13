import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from packages.shared_types.crm import SignalType
from services.api.app.agents.signals.urgency import UrgencyDetector, UrgencyLevel, UrgencyResult


class DetectedSignal(BaseModel):
    """Normalized detected buying or need signal."""
    signal_type: SignalType
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: str
    source_url: Optional[str] = None
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# False positive indicator categories and patterns (competitors, job seekers, students, casual consumers)
DISQUALIFYING_CATEGORIES = {
    "STUDENT": r"\b(for school|homework|class project|school assignment|student project|college assignment|college project|studying for|cs student|college class|college homework)\b",
    "JOB_SEEKER": r"\b(resume|cv|applying for|looking for (an? )?([a-z\-_]+\s+)*job|seeking (a )?([a-z\-_]+\s+)*job|seeking employment|internship|hire me as a developer|seeking a position|open to work|#opentowork)\b",
    "FREELANCER": r"\b(i am|i'm|as a)\s+(a\s+)?(freelance\s+)?(web developer|web designer|developer|designer|freelancer|software engineer)\s+(looking for|seeking|available for)\s+(clients|work|projects)\b|\b(hire me|my portfolio|check out my portfolio|freelancer available|freelance developer available|freelance designer available)\b",
    "DEVELOPER_SELF_PROMO": r"\b(i (build|design|create|make|develop)\s+(websites|apps|mobile apps|software|landing pages)|(hire|dm|contact)\s+me\s+(to|for|if you need)|open for (freelance|work|clients|projects)|available for (freelance|hire|new projects)|check out my (latest|recent)?\s*(work|projects|portfolio)|my services include|offering (web|app|development|design) services|freelance (web developer|designer|engineer) available)\b",
    "COMPETITOR_AGENCY": r"\b(our agency offers|we are a web design agency|we are a digital agency|dm us for web dev|marketing agency here to help|we provide seo services)\b",
    "CONSUMER_HELP": r"\b(anyone know a good website (to|for|where|that))\s+(watch|stream|play|download|read|buy shoes|find movies)\b|\b(personal help|for my own personal use)\b",
    "ALREADY_BUILT": r"\b(i built|we already built|just launched|finished building)\s+(my|our|a)\s+(website|app)\b",
    "EDUCATIONAL_TIPS": r"\b(before you hire|how to hire|tips (for|on) hiring|when (to hire|you hire)|how do you know you need|reasons why you need|why you need a|here('s| is) why you need|(?:\d+|five|three|four|ten|few) things to|questions to ask (a|your)?\s*(developer|designer|agency)|send these (?:\d+|five|three|four|ten|few) things|tips for building|here are (?:\d+|five|three|four|ten|few) (tips|reasons|mistakes))\b",
    "PROMOTIONAL_MEDIA": r"\b(podcast for|listen to (our|the|this)?\s*podcast|new episode of|check out our podcast|subscribe to our (podcast|channel|newsletter)|on this episode|watch the full episode)\b",
    "AGENCY_SELF_PROMO": r"\b(we help (brands|startups|companies|businesses)|we design and build|transform your (online|brand|business)|reach out to us for|book a (call|consultation) (with us|today)|link in bio to (work with us|book|get started))\b",
}

DISQUALIFYING_PATTERNS = list(DISQUALIFYING_CATEGORIES.values())
DISQUALIFYING_REGEX = re.compile("|".join(DISQUALIFYING_PATTERNS), re.IGNORECASE)


# Rules for all 18 signal types
SIGNAL_TAXONOMY_RULES: List[Dict[str, Any]] = [
    {
        "type": SignalType.WEBSITE_REQUEST,
        "pattern": r"\b(need|looking for|lf|want|hire|seeking|recommend\s+(?:someone|anyone)\s+who\s+can\s+(?:build|make|develop|redesign))\s+(?:an?|the|our)?\s*(?:[a-zA-Z0-9-]+\s+)?(website|web site|site|landing page|marketing site|web developer|web designer|web dev)\b|\b(?:looking for\s+)?someone to build\s+(?:an?|the|our)?\s*(?:[a-zA-Z0-9-]+\s+)?(website|site|landing page|marketing site|web\s*app)\b|\b(build|develop|redesign)\s+(?:me|us|our|a|the)?\s*(?:[a-zA-Z0-9-]+\s+)?(website|site|landing page|marketing site)\b",
        "confidence": 0.95,
        "template": "Explicit public request seeking a website or web developer.",
    },
    {
        "type": SignalType.WEBSITE_OUTDATED,
        "pattern": r"\b(redesign(ing)?|revamp(ing)?|rebuild(ing)?|re-design|our\s+site\s+looks\s+(old|ancient|dated|90s)|haven't\s+updated\s+our\s+website\s+in\s+years|website redesign request)\b",
        "confidence": 0.92,
        "template": "Evidence of outdated design or explicit need for website redesign.",
    },
    {
        "type": SignalType.APP_DEVELOPMENT_REQUEST,
        "pattern": r"\b(need|looking for|lf|build|develop|seeking|hire|recommend\s+(?:someone|anyone)\s+who\s+can\s+(?:build|make|develop))\s+(?:an?|the|our)?\s*(?:[a-zA-Z0-9-]+\s+)?(app|mobile app|web app|ios app|android app|react native app|flutter app|app developer|application)\b|\b(?:someone|anyone)\s+who\s+can\s+(?:build|make|develop)\s+(?:an?|the|our)?\s*(?:[a-zA-Z0-9-]+\s+)?(app|mobile app|web app|application)\b",
        "confidence": 0.94,
        "template": "Request identified for custom application development.",
    },
    {
        "type": SignalType.AI_AUTOMATION_REQUEST,
        "pattern": r"\b(ai\s+automation|automate\s+(my|our)\s+workflows?|ai\s+agents?|custom\s+llm|ai\s+bot|automation\s+agency|ai automation requirement)\b",
        "confidence": 0.93,
        "template": "Business seeking AI automation or agentic workflow development.",
    },
    {
        "type": SignalType.HIRING_DEVELOPER,
        "pattern": r"\b(hiring|looking to hire|we're hiring|lf|looking for|need)\s+(a\s+)?(developer|frontend|backend|fullstack|software engineer|tech lead)\b",
        "confidence": 0.90,
        "template": "Active hiring posting for software or web development talent.",
    },
    {
        "type": SignalType.HIRING_DESIGNER,
        "pattern": r"\b(hiring|looking to hire|we're hiring|lf|looking for|need)\s+(a\s+)?(ui\/?ux designer|product designer|web designer|graphic designer|designer)\b",
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
        "pattern": r"\b(recommend|looking for|lf|seeking|need|hiring)\s+(?:an?\s+)?(?:[a-zA-Z0-9_\-\/]+\s+)*(?:agency|consultant|service provider|technical partner|dev shop|creator|editor|video editor|creators\/editors|video creator|partner|talent|freelancer)\b",
        "confidence": 0.89,
        "template": "Public request for specialized service provider, creative editor, or technical partner.",
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
    def classify_disqualification(cls, text: str) -> Optional[str]:
        """Return human-readable explanation of why a candidate was disqualified."""
        if not text:
            return None
        clean = cls.sanitize_text(text)
        for cat, pattern in DISQUALIFYING_CATEGORIES.items():
            if re.search(pattern, clean, re.IGNORECASE):
                if cat == "STUDENT":
                    return "Student / academic homework project"
                elif cat == "JOB_SEEKER":
                    return "Job seeker looking for employment"
                elif cat == "FREELANCER":
                    return "Freelancer looking for clients / work"
                elif cat == "DEVELOPER_SELF_PROMO":
                    return "Developer advertising their own services"
                elif cat == "COMPETITOR_AGENCY":
                    return "Competitor agency / service provider"
                elif cat == "CONSUMER_HELP":
                    return "Consumer personal help inquiry"
                elif cat == "ALREADY_BUILT":
                    return "Already built website / project finished"
                return f"Disqualified: {cat}"
        return None

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

    BUYING_INTENT_SIGNALS = {
        SignalType.WEBSITE_REQUEST,
        SignalType.APP_DEVELOPMENT_REQUEST,
        SignalType.AI_AUTOMATION_REQUEST,
        SignalType.ECOMMERCE_OPPORTUNITY,
        SignalType.REQUEST_FOR_SERVICE,
        SignalType.HIRING_DEVELOPER,
        SignalType.HIRING_DESIGNER,
    }

    GROWTH_SIGNALS = {
        SignalType.BUSINESS_LAUNCH,
        SignalType.NEW_PRODUCT,
        SignalType.BUSINESS_EXPANSION,
        SignalType.GROWTH_SIGNAL,
        SignalType.RECENT_FUNDING,
    }

    HIRING_SIGNALS = {
        SignalType.HIRING_DEVELOPER,
        SignalType.HIRING_DESIGNER,
    }

    TECHNICAL_SIGNALS = {
        SignalType.WEBSITE_OUTDATED,
        SignalType.WEBSITE_SLOW,
        SignalType.POOR_MOBILE_UX,
        SignalType.WEAK_CONVERSION,
        SignalType.WEAK_SEO,
        SignalType.TECH_STACK_CHANGE,
    }

    @classmethod
    def classify_signals(cls, signals: List[DetectedSignal]) -> Dict[str, List[DetectedSignal]]:
        """Group detected signals into intent, growth, hiring, and technical categories."""
        grouped: Dict[str, List[DetectedSignal]] = {
            "buying_intent": [],
            "growth": [],
            "hiring": [],
            "technical": [],
        }
        for sig in signals:
            if sig.signal_type in cls.BUYING_INTENT_SIGNALS:
                grouped["buying_intent"].append(sig)
            elif sig.signal_type in cls.GROWTH_SIGNALS:
                grouped["growth"].append(sig)
            elif sig.signal_type in cls.HIRING_SIGNALS:
                grouped["hiring"].append(sig)
            elif sig.signal_type in cls.TECHNICAL_SIGNALS:
                grouped["technical"].append(sig)
        return grouped

    @classmethod
    def has_explicit_intent(cls, signals: List[DetectedSignal]) -> bool:
        """True if at least one high-intent buying or service request signal was detected."""
        return any(sig.signal_type in cls.BUYING_INTENT_SIGNALS for sig in signals)

    @classmethod
    def evaluate_urgency(cls, text: Optional[str]) -> UrgencyResult:
        """Deterministically assess temporal and business urgency backed by observable evidence."""
        return UrgencyDetector.evaluate(text)

