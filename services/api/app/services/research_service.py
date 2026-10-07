import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared_types.crm import SignalType
from services.api.app.agents.research.research_engine import ResearchEngine
from services.api.app.agents.research.research_models import ResearchStatus
from services.api.app.agents.research.validators import (
    SSRFValidationError,
    validate_and_sanitize_target_url,
)
from services.api.app.agents.research.website_researcher import WebsiteResearcher
from services.api.app.models.research import WebsitePageResearch, WebsiteResearch
from services.api.app.repositories.crm import CompanyRepository, LeadRepository
from services.api.app.repositories.research import WebsiteResearchRepository
from services.api.app.schemas.crm import LeadSignalCreate
from services.api.app.services.crm_service import EntityNotFoundException, LeadService
from services.api.app.services.event_dispatcher import EventDispatcher


class ResearchService:
    """Orchestrates website intelligence, persistence, score updating, and domain event dispatch."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.research_repo = WebsiteResearchRepository(session)
        self.lead_repo = LeadRepository(session)
        self.lead_service = LeadService(session)

    async def execute_lead_website_research(
        self,
        lead_id: uuid.UUID,
        org_id: uuid.UUID,
        override_url: Optional[str] = None,
        pages_data: Optional[List[Dict[str, Any]]] = None,
        force_recheck: bool = False,
    ) -> WebsiteResearch:
        # 1. Fetch lead & associated company
        lead = await self.lead_repo.get_by_id(org_id, lead_id)
        if not lead:
            raise EntityNotFoundException("Lead", lead_id)

        company = None
        if lead.company_id:
            company_repo = CompanyRepository(self.session)
            company = await company_repo.get_by_id(org_id, lead.company_id)

        # 2. Resolve target website URL
        resolved_url = None
        if override_url:
            resolved_url = validate_and_sanitize_target_url(override_url)
        else:
            company_domain = company.domain if company else None
            meta = company.metadata_json if (company and company.metadata_json) else {}
            resolution = WebsiteResearcher.resolve_website(
                company_domain=company_domain,
                profile_url=lead.profile_url,
                source_url=lead.source_url,
                metadata_json=meta,
            )
            if resolution.found and resolution.primary_url:
                resolved_url = resolution.primary_url
            elif lead.profile_url and ("http://" in lead.profile_url or "https://" in lead.profile_url):
                # Try profile URL if external site
                try:
                    resolved_url = validate_and_sanitize_target_url(lead.profile_url)
                except SSRFValidationError:
                    resolved_url = None

        if not resolved_url:
            raise ValueError(f"No valid public website could be resolved for lead {lead_id}")

        correlation_id = str(uuid.uuid4())

        # 3. Emit research started & website resolved events
        await EventDispatcher.emit(
            event_type="lead.research.started",
            org_id=org_id,
            lead_id=lead_id,
            payload={"correlation_id": correlation_id, "website_url": resolved_url},
        )
        await EventDispatcher.emit(
            event_type="lead.website.resolved",
            org_id=org_id,
            lead_id=lead_id,
            payload={"correlation_id": correlation_id, "website_url": resolved_url},
        )

        company_name = company.name if company else lead.title

        # 4. Run Technical Research Engine
        res = ResearchEngine.execute_research(
            website_url=resolved_url,
            pages_data=pages_data,
            company_name=company_name,
        )

        # 5. Persist WebsiteResearch record
        research_record = WebsiteResearch(
            organization_id=org_id,
            lead_id=lead_id,
            company_id=lead.company_id,
            website_url=resolved_url,
            status=ResearchStatus.COMPLETED.value,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            pages_analyzed=res["pages_analyzed"],
            pages_failed=res["pages_failed"],
            technology_stack=res["technology_stack"],
            cms=res["cms"],
            frontend_framework=res["frontend_framework"],
            backend_technology=res["backend_technology"],
            analytics_tools=res["analytics_tools"],
            payment_provider=res["payment_provider"],
            cdn=res["cdn"],
            ecommerce_platform=res["ecommerce_platform"],
            website_health_score=res["scores"].website_health_score,
            performance_score=res["scores"].performance_score,
            mobile_score=res["scores"].mobile_score,
            ux_score=res["scores"].ux_score,
            seo_score=res["scores"].seo_score,
            conversion_score=res["scores"].conversion_score,
            accessibility_score=res["scores"].accessibility_score,
            opportunity_score=res["opportunity_breakdown"].total_opportunity_score,
            summary=res["summary"],
            positive_findings=res["positive_findings"],
            negative_findings=res["negative_findings"],
            recommendations=res["recommendations"],
            confidence=res["confidence"],
        )
        await self.research_repo.create_research(research_record)

        # 6. Persist individual page results
        for page_data in res["analyzed_pages"]:
            page_rec = WebsitePageResearch(
                research_id=research_record.id,
                organization_id=org_id,
                url=page_data.url,
                page_type=page_data.page_type,
                title=page_data.title,
                status_code=page_data.status_code,
                content_summary=page_data.content_summary,
                visible_text=page_data.visible_text[:2000] if page_data.visible_text else None,
                links_count=page_data.links_count,
                has_cta=page_data.has_cta,
                has_contact_form=page_data.has_contact_form,
                has_phone=page_data.has_phone,
                has_email=page_data.has_email,
                has_pricing=page_data.has_pricing,
                has_product_catalog=page_data.has_product_catalog,
                has_checkout=page_data.has_checkout,
                has_social_proof=page_data.has_social_proof,
                has_testimonials=page_data.has_testimonials,
                has_reviews=page_data.has_reviews,
                mobile_observations=page_data.mobile_observations,
                ux_observations=page_data.ux_observations,
                seo_observations=page_data.seo_observations,
                performance_observations=page_data.performance_observations,
                conversion_observations=page_data.conversion_observations,
            )
            await self.research_repo.add_page_research(page_rec)

            await EventDispatcher.emit(
                event_type="lead.page.analyzed",
                org_id=org_id,
                lead_id=lead_id,
                payload={"page_url": page_data.url, "page_type": page_data.page_type},
            )

        # 7. Add discovered signals into Lead CRM
        for sig in res["generated_signals"]:
            sig_type = SignalType(sig["signal_type"]) if isinstance(sig["signal_type"], str) else sig["signal_type"]
            sig_create = LeadSignalCreate(
                lead_id=lead_id,
                signal_type=sig_type,
                confidence=sig["confidence"],
                evidence=sig["evidence"],
                source_url=sig["source_url"],
            )
            await self.lead_service.add_signal(org_id, sig_create)
            await EventDispatcher.emit(
                event_type="lead.website.signal.detected",
                org_id=org_id,
                lead_id=lead_id,
                payload={"signal_type": sig_type.value, "confidence": sig["confidence"]},
            )

        # 8. Dispatch technology & audit domain events
        await EventDispatcher.emit(
            event_type="lead.technology.detected",
            org_id=org_id,
            lead_id=lead_id,
            payload={"technology_stack": res["technology_stack"]},
        )
        await EventDispatcher.emit(
            event_type="lead.website.audit.completed",
            org_id=org_id,
            lead_id=lead_id,
            payload={
                "health_score": res["scores"].website_health_score,
                "opportunity_score": res["opportunity_breakdown"].total_opportunity_score,
            },
        )
        await EventDispatcher.emit(
            event_type="lead.website.opportunity.updated",
            org_id=org_id,
            lead_id=lead_id,
            payload={"opportunity_score": res["opportunity_breakdown"].total_opportunity_score},
        )

        # 9. Recalculate Lead Score & Service Match via Phase 3
        reason = (
            f"Website research completed. Opportunity: {res['opportunity_breakdown'].total_opportunity_score}/100, "
            f"Health: {res['scores'].website_health_score}/100. Discovered {len(res['generated_signals'])} website signals."
        )
        scored_lead, qual = await self.lead_service.score_lead(org_id=org_id, lead_id=lead_id, reason=reason)
        service_match = await self.lead_service.get_service_match(org_id=org_id, lead_id=lead_id)

        await EventDispatcher.emit(
            event_type="lead.score.updated",
            org_id=org_id,
            lead_id=lead_id,
            payload={"overall_score": scored_lead.overall_score},
        )
        await EventDispatcher.emit(
            event_type="lead.service.matched",
            org_id=org_id,
            lead_id=lead_id,
            payload={"recommended_service": service_match.recommended_service},
        )
        await EventDispatcher.emit(
            event_type="lead.qualification.updated",
            org_id=org_id,
            lead_id=lead_id,
            payload={"category": qual.category, "qualified": qual.qualified},
        )
        await EventDispatcher.emit(
            event_type="lead.research.completed",
            org_id=org_id,
            lead_id=lead_id,
            payload={"research_id": str(research_record.id), "status": "COMPLETED"},
        )

        await self.session.commit()
        return research_record

    async def get_latest_research(self, lead_id: uuid.UUID, org_id: uuid.UUID) -> Optional[WebsiteResearch]:
        lead = await self.lead_repo.get_by_id(org_id, lead_id)
        if not lead:
            raise EntityNotFoundException("Lead", lead_id)
        return await self.research_repo.get_latest_for_lead(lead_id, org_id)

    async def list_research_history(self, lead_id: uuid.UUID, org_id: uuid.UUID) -> List[WebsiteResearch]:
        lead = await self.lead_repo.get_by_id(org_id, lead_id)
        if not lead:
            raise EntityNotFoundException("Lead", lead_id)
        return await self.research_repo.list_history_for_lead(lead_id, org_id)

    async def get_research_pages(self, lead_id: uuid.UUID, org_id: uuid.UUID) -> List[WebsitePageResearch]:
        latest = await self.get_latest_research(lead_id, org_id)
        if not latest:
            return []
        return await self.research_repo.get_pages_for_research(latest.id, org_id)
