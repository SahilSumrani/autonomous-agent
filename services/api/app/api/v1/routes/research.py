import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.agents.research.validators import SSRFValidationError
from services.api.app.api.v1.dependencies.auth import get_current_org_id
from services.api.app.core.database import get_db
from services.api.app.schemas.research import (
    ResearchInitiateRequest,
    TechnologyStackResponse,
    WebsiteAuditResponse,
    WebsiteOpportunityResponse,
    WebsitePageResearchResponse,
    WebsiteResearchResponse,
)
from services.api.app.services.crm_service import EntityNotFoundException
from services.api.app.services.research_service import ResearchService
from services.api.app.services.website_intelligence import WebsiteIntelligenceService

router = APIRouter(prefix="/leads", tags=["Website Research"])


@router.post("/{lead_id}/research", response_model=WebsiteResearchResponse, status_code=status.HTTP_201_CREATED)
async def initiate_lead_research(
    lead_id: uuid.UUID,
    data: Optional[ResearchInitiateRequest] = None,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> WebsiteResearchResponse:
    """Initiates deep technical research and audit on the lead's website."""
    service = ResearchService(db)
    override_url = data.website_url if data else None
    pages_data = data.pages_data if data else None
    force_recheck = data.force_recheck if data else False

    try:
        research = await service.execute_lead_website_research(
            lead_id=lead_id,
            org_id=org_id,
            override_url=override_url,
            pages_data=pages_data,
            force_recheck=force_recheck,
        )
        return WebsiteResearchResponse.model_validate(research)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except SSRFValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"SSRF validation blocked target URL: {e}")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{lead_id}/research", response_model=WebsiteResearchResponse)
async def get_latest_research(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> WebsiteResearchResponse:
    """Retrieves the latest website research analysis for a lead."""
    service = ResearchService(db)
    try:
        research = await service.get_latest_research(lead_id, org_id)
        if not research:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No website research found for lead {lead_id}",
            )
        return WebsiteResearchResponse.model_validate(research)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{lead_id}/research/history", response_model=List[WebsiteResearchResponse])
async def list_research_history(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> List[WebsiteResearchResponse]:
    """Retrieves all historical website research runs for a lead."""
    service = ResearchService(db)
    try:
        history = await service.list_research_history(lead_id, org_id)
        return [WebsiteResearchResponse.model_validate(r) for r in history]
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{lead_id}/research/pages", response_model=List[WebsitePageResearchResponse])
async def get_research_pages(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> List[WebsitePageResearchResponse]:
    """Retrieves detailed per-page findings from the latest website research audit."""
    service = ResearchService(db)
    try:
        pages = await service.get_research_pages(lead_id, org_id)
        return [WebsitePageResearchResponse.model_validate(p) for p in pages]
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{lead_id}/research/technology", response_model=TechnologyStackResponse)
async def get_research_technology(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> TechnologyStackResponse:
    """Retrieves detected technology, frameworks, and analytics for the lead's website."""
    intel_service = WebsiteIntelligenceService(db)
    try:
        return await intel_service.get_technology_stack(lead_id, org_id)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{lead_id}/research/audit", response_model=WebsiteAuditResponse)
async def get_research_audit(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> WebsiteAuditResponse:
    """Retrieves category health scores and positive/negative findings."""
    intel_service = WebsiteIntelligenceService(db)
    try:
        return await intel_service.get_audit(lead_id, org_id)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{lead_id}/research/opportunities", response_model=WebsiteOpportunityResponse)
async def get_research_opportunities(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> WebsiteOpportunityResponse:
    """Retrieves deterministic opportunity scores and improvement reasons."""
    intel_service = WebsiteIntelligenceService(db)
    try:
        return await intel_service.get_opportunities(lead_id, org_id)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{lead_id}/research/re-run", response_model=WebsiteResearchResponse, status_code=status.HTTP_201_CREATED)
async def rerun_lead_research(
    lead_id: uuid.UUID,
    data: Optional[ResearchInitiateRequest] = None,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> WebsiteResearchResponse:
    """Forces a fresh website research run, creating a new historical record."""
    service = ResearchService(db)
    override_url = data.website_url if data else None
    pages_data = data.pages_data if data else None

    try:
        research = await service.execute_lead_website_research(
            lead_id=lead_id,
            org_id=org_id,
            override_url=override_url,
            pages_data=pages_data,
            force_recheck=True,
        )
        return WebsiteResearchResponse.model_validate(research)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except SSRFValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"SSRF validation blocked target URL: {e}")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
