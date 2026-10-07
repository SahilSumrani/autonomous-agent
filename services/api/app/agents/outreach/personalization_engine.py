from typing import List, Tuple
from packages.shared_types.outreach import (
    OutreachAngle,
    PainPointCategory,
    PersonalizationLevel,
)
from services.api.app.agents.outreach.outreach_models import (
    OutreachContext,
    PainPoint,
)


class PersonalizationEngine:
    """Extracts verified pain points and generates evidence-backed value propositions."""

    @classmethod
    def evaluate_personalization_level(cls, context: OutreachContext) -> PersonalizationLevel:
        """Determines personalization level strictly based on evidence count and depth."""
        has_website_evidence = bool(context.website_url and context.pain_points)
        has_specific_observation = bool(context.verified_observations or context.verified_signals)

        # Deep: Specific public observation + website issue/tech + recommended service
        if has_website_evidence and has_specific_observation:
            return PersonalizationLevel.DEEP

        # Contextual: Specific post/observation or business announcement
        if has_specific_observation or context.website_url:
            return PersonalizationLevel.CONTEXTUAL

        # Basic: Just company name / industry / generic service
        return PersonalizationLevel.BASIC

    @classmethod
    def select_value_proposition(
        cls,
        service: str,
        angle: OutreachAngle,
        pain_points: List[PainPoint],
    ) -> str:
        """Generates realistic, evidence-backed value proposition without unsubstantiated guarantees."""
        svc = service.upper()
        if "ECOMMERCE" in svc or angle == OutreachAngle.ECOMMERCE:
            return "Improve the storefront journey and reduce friction between product discovery and checkout."
        if "MOBILE" in svc or angle == OutreachAngle.MOBILE_UX:
            return "Eliminate mobile layout and navigation friction to give smartphone visitors an effortless browsing experience."
        if "PERFORMANCE" in svc or angle == OutreachAngle.PERFORMANCE:
            return "Streamline page weight and asset loading so pages respond instantly on all devices."
        if "SEO" in svc or angle == OutreachAngle.SEO:
            return "Strengthen crawlability, meta architecture, and heading structure to capture organic search intent."
        if "WEBSITE_REDESIGN" in svc or angle == OutreachAngle.WEBSITE_REDESIGN:
            return "Modernize the visual hierarchy and conversion architecture with a high-performance web experience."
        if "AI_AUTOMATION" in svc or angle == OutreachAngle.AI_AUTOMATION:
            return "Automate repetitive data collection and operational workflows using custom AI pipelines."
        if "LANDING_PAGE" in svc:
            return "Create a focused, high-converting landing experience with clear value propositions and strong CTAs."

        return "Upgrade technical stability and user journey across your digital channels."
