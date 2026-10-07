import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.models.research import WebsiteResearch
from services.api.app.schemas.research import (
    TechnologyStackResponse,
    WebsiteAuditResponse,
    WebsiteOpportunityResponse,
    WebsiteResearchResponse,
)
from services.api.app.services.research_service import ResearchService


class WebsiteIntelligenceService:
    """Convenience facade for querying and formatting website research findings."""

    def __init__(self, session: AsyncSession):
        self.research_service = ResearchService(session)

    async def get_technology_stack(
        self, lead_id: uuid.UUID, org_id: uuid.UUID
    ) -> TechnologyStackResponse:
        latest = await self.research_service.get_latest_research(lead_id, org_id)
        if not latest:
            return TechnologyStackResponse()

        return TechnologyStackResponse(
            technology_stack=latest.technology_stack or [],
            cms=latest.cms,
            frontend_framework=latest.frontend_framework,
            backend_technology=latest.backend_technology,
            analytics_tools=latest.analytics_tools or [],
            payment_provider=latest.payment_provider,
            hosting_provider=latest.hosting_provider,
            cdn=latest.cdn,
            ecommerce_platform=latest.ecommerce_platform,
        )

    async def get_audit(
        self, lead_id: uuid.UUID, org_id: uuid.UUID
    ) -> WebsiteAuditResponse:
        latest = await self.research_service.get_latest_research(lead_id, org_id)
        if not latest:
            return WebsiteAuditResponse()

        return WebsiteAuditResponse(
            website_health_score=latest.website_health_score,
            performance_score=latest.performance_score,
            mobile_score=latest.mobile_score,
            ux_score=latest.ux_score,
            seo_score=latest.seo_score,
            conversion_score=latest.conversion_score,
            accessibility_score=latest.accessibility_score,
            positive_findings=latest.positive_findings or [],
            negative_findings=latest.negative_findings or [],
            recommendations=latest.recommendations or [],
        )

    async def get_opportunities(
        self, lead_id: uuid.UUID, org_id: uuid.UUID
    ) -> WebsiteOpportunityResponse:
        latest = await self.research_service.get_latest_research(lead_id, org_id)
        if not latest:
            return WebsiteOpportunityResponse()

        return WebsiteOpportunityResponse(
            opportunity_score=latest.opportunity_score,
            breakdown={
                "performance_score": latest.performance_score,
                "mobile_score": latest.mobile_score,
                "ux_score": latest.ux_score,
                "seo_score": latest.seo_score,
                "conversion_score": latest.conversion_score,
            },
            reasons=latest.recommendations or [],
        )
