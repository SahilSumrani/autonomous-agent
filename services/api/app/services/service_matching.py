from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from packages.shared_types.crm import SignalType, TechVerseService


class ServiceCatalogItem(BaseModel):
    """Metadata definition for a TechVerse commercial service offering."""
    service_id: TechVerseService
    name: str
    description: str
    ideal_customer: str
    target_signals: List[SignalType]
    price_range: str
    priority: int


SERVICE_CATALOG: Dict[TechVerseService, ServiceCatalogItem] = {
    TechVerseService.ECOMMERCE: ServiceCatalogItem(
        service_id=TechVerseService.ECOMMERCE,
        name="E-Commerce & Digital Storefronts",
        description="High-converting modern e-commerce stores with optimized checkout and catalog architecture.",
        ideal_customer="Apparel, retail, and physical product brands launching or upgrading online sales.",
        target_signals=[SignalType.ECOMMERCE_OPPORTUNITY, SignalType.BUSINESS_LAUNCH, SignalType.NEW_PRODUCT],
        price_range="$3,500 - $12,000",
        priority=10,
    ),
    TechVerseService.AI_AUTOMATION: ServiceCatalogItem(
        service_id=TechVerseService.AI_AUTOMATION,
        name="AI & Agentic Operations Automation",
        description="Bespoke agentic automation pipelines eliminating repetitive operational workflows.",
        ideal_customer="Growing businesses, agencies, and operators needing streamlined AI workflows.",
        target_signals=[SignalType.AI_AUTOMATION_REQUEST, SignalType.GROWTH_SIGNAL],
        price_range="$5,000 - $20,000",
        priority=10,
    ),
    TechVerseService.WEBSITE_REDESIGN: ServiceCatalogItem(
        service_id=TechVerseService.WEBSITE_REDESIGN,
        name="Modern Website Redesign & Overhaul",
        description="Complete structural and aesthetic rebuild replacing outdated, slow, or poorly converting websites.",
        ideal_customer="Established businesses suffering from obsolete design or poor conversion metrics.",
        target_signals=[SignalType.WEBSITE_OUTDATED, SignalType.WEBSITE_SLOW, SignalType.POOR_MOBILE_UX, SignalType.WEAK_CONVERSION],
        price_range="$3,000 - $10,000",
        priority=9,
    ),
    TechVerseService.BUSINESS_WEBSITE: ServiceCatalogItem(
        service_id=TechVerseService.BUSINESS_WEBSITE,
        name="High-Performance Business Website",
        description="Fast, bespoke web platform establishing credible digital authority and generating leads.",
        ideal_customer="Commercial services, founders, consultancies, and new venture launches.",
        target_signals=[SignalType.WEBSITE_REQUEST, SignalType.BUSINESS_LAUNCH, SignalType.HIRING_DEVELOPER],
        price_range="$2,500 - $8,000",
        priority=8,
    ),
    TechVerseService.MOBILE_APP: ServiceCatalogItem(
        service_id=TechVerseService.MOBILE_APP,
        name="Custom Mobile Application",
        description="Native-grade iOS & Android applications built with robust backend architectures.",
        ideal_customer="Product startups and businesses launching mobile-first customer experiences.",
        target_signals=[SignalType.APP_DEVELOPMENT_REQUEST],
        price_range="$8,000 - $35,000",
        priority=8,
    ),
    TechVerseService.PERFORMANCE_OPTIMIZATION: ServiceCatalogItem(
        service_id=TechVerseService.PERFORMANCE_OPTIMIZATION,
        name="Web Performance & Speed Optimization",
        description="Core Web Vitals tuning, caching, and server architecture optimization for slow sites.",
        ideal_customer="Websites losing customers due to high latency and sluggish load times.",
        target_signals=[SignalType.WEBSITE_SLOW, SignalType.POOR_MOBILE_UX],
        price_range="$1,500 - $5,000",
        priority=6,
    ),
    TechVerseService.PREMIUM_WEBSITE: ServiceCatalogItem(
        service_id=TechVerseService.PREMIUM_WEBSITE,
        name="Premium Interactive Web Experience",
        description="High-end bespoke digital experience with custom 3D animations, rich micro-interactions, and executive branding.",
        ideal_customer="Luxury brands, funded startups, and industry leaders seeking standout digital presence.",
        target_signals=[SignalType.RECENT_FUNDING, SignalType.BUSINESS_EXPANSION],
        price_range="$6,000 - $25,000",
        priority=9,
    ),
    TechVerseService.WEB_APP: ServiceCatalogItem(
        service_id=TechVerseService.WEB_APP,
        name="Custom Fullstack Web Application",
        description="Scalable SaaS platforms, portal architectures, and interactive internal toolings.",
        ideal_customer="Startups building software products or businesses digitizing internal systems.",
        target_signals=[SignalType.TECH_STACK_CHANGE, SignalType.HIRING_DEVELOPER],
        price_range="$7,000 - $30,000",
        priority=8,
    ),
    TechVerseService.CUSTOM_AI_PRODUCT: ServiceCatalogItem(
        service_id=TechVerseService.CUSTOM_AI_PRODUCT,
        name="Custom AI Product / MVP",
        description="AI-native customer-facing web products incorporating LLMs, RAG, and agentic workflows.",
        ideal_customer="Founders launching AI-powered SaaS or productized offerings.",
        target_signals=[SignalType.AI_AUTOMATION_REQUEST, SignalType.NEW_PRODUCT],
        price_range="$10,000 - $40,000",
        priority=10,
    ),
    TechVerseService.SEO: ServiceCatalogItem(
        service_id=TechVerseService.SEO,
        name="Technical SEO & Visibility Acceleration",
        description="Search engine architecture, schema markup, performance tuning, and content discoverability.",
        ideal_customer="Businesses seeking organic client acquisition and search authority.",
        target_signals=[SignalType.WEAK_SEO],
        price_range="$1,500 - $4,500",
        priority=5,
    ),
    TechVerseService.LANDING_PAGE: ServiceCatalogItem(
        service_id=TechVerseService.LANDING_PAGE,
        name="Conversion Landing Page",
        description="Focused, single-purpose landing page engineered specifically for ad conversions or waitlists.",
        ideal_customer="New product launches, waitlists, and targeted marketing campaigns.",
        target_signals=[SignalType.NEW_PRODUCT],
        price_range="$1,200 - $3,000",
        priority=5,
    ),
}


class ServiceMatchResult(BaseModel):
    """Structured service recommendation result."""
    recommended_service: TechVerseService
    alternative_services: List[TechVerseService] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str


class ServiceMatchingEngine:
    """Matches identified signals and business context to optimal TechVerse offerings."""

    @classmethod
    def match_service(
        cls,
        signals: Any,
        business_context: Optional[str] = None,
        text: Optional[str] = None,
    ) -> ServiceMatchResult:
        """Evaluate detected signals to determine primary and alternative service fits."""
        context = business_context or text or ""

        # Normalize signals to Set[SignalType]
        normalized_signal_types = set()
        if signals:
            for s in signals:
                if isinstance(s, SignalType):
                    normalized_signal_types.add(s)
                elif hasattr(s, "signal_type"):
                    sig_val = s.signal_type
                    if isinstance(sig_val, SignalType):
                        normalized_signal_types.add(sig_val)
                    elif isinstance(sig_val, str) and sig_val in SignalType.__members__:
                        normalized_signal_types.add(SignalType(sig_val))

        if not normalized_signal_types:
            return ServiceMatchResult(
                recommended_service=TechVerseService.BUSINESS_WEBSITE,
                alternative_services=[TechVerseService.LANDING_PAGE],
                confidence=0.50,
                reason="Default baseline recommendation for general commercial presence.",
            )

        signal_set = normalized_signal_types

        # 1. Check AI Automation
        if SignalType.AI_AUTOMATION_REQUEST in signal_set:
            return ServiceMatchResult(
                recommended_service=TechVerseService.AI_AUTOMATION,
                alternative_services=[TechVerseService.BUSINESS_WEBSITE],
                confidence=0.94,
                reason="Explicit interest or requirement in AI automation pipelines.",
            )

        # 2. Check Mobile App
        if SignalType.APP_DEVELOPMENT_REQUEST in signal_set:
            return ServiceMatchResult(
                recommended_service=TechVerseService.MOBILE_APP,
                alternative_services=[TechVerseService.WEB_APP],
                confidence=0.93,
                reason="Explicit request for custom mobile application development.",
            )

        # 3. Check E-Commerce
        if SignalType.ECOMMERCE_OPPORTUNITY in signal_set or (
            SignalType.BUSINESS_LAUNCH in signal_set and any(w in context.lower() for w in ["store", "clothing", "shop", "brand"])
        ):
            return ServiceMatchResult(
                recommended_service=TechVerseService.ECOMMERCE,
                alternative_services=[TechVerseService.BUSINESS_WEBSITE],
                confidence=0.92,
                reason="Product storefront or e-commerce requirement identified.",
            )

        # 4. Check Website Redesign
        if any(s in signal_set for s in [SignalType.WEBSITE_OUTDATED, SignalType.WEBSITE_SLOW, SignalType.POOR_MOBILE_UX, SignalType.WEAK_CONVERSION]):
            return ServiceMatchResult(
                recommended_service=TechVerseService.WEBSITE_REDESIGN,
                alternative_services=[TechVerseService.PERFORMANCE_OPTIMIZATION, TechVerseService.BUSINESS_WEBSITE],
                confidence=0.91,
                reason="Observable pain points with existing website design, mobile UX, or conversion.",
            )

        # 5. Check Website Request / Launch
        if any(s in signal_set for s in [SignalType.WEBSITE_REQUEST, SignalType.BUSINESS_LAUNCH, SignalType.HIRING_DEVELOPER]):
            return ServiceMatchResult(
                recommended_service=TechVerseService.BUSINESS_WEBSITE,
                alternative_services=[TechVerseService.PREMIUM_WEBSITE, TechVerseService.LANDING_PAGE],
                confidence=0.90,
                reason="Active requirement or launch milestone necessitating a professional business website.",
            )

        # 6. Fallback
        return ServiceMatchResult(
            recommended_service=TechVerseService.BUSINESS_WEBSITE,
            alternative_services=[TechVerseService.LANDING_PAGE],
            confidence=0.70,
            reason="Commercial opportunity aligned with primary web development capabilities.",
        )

    match = match_service
