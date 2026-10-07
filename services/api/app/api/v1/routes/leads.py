import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared_types.crm import LeadStatus, LeadType
from services.api.app.api.v1.dependencies.auth import get_current_org_id
from services.api.app.core.database import get_db
from services.api.app.schemas.crm import (
    LeadCreate,
    LeadResponse,
    LeadSignalCreate,
    LeadSignalResponse,
    LeadStatusUpdate,
    LeadUpdate,
    PaginatedResponse,
    PipelineEventResponse,
)
from services.api.app.services.crm_service import (
    DuplicateEntityException,
    EntityNotFoundException,
    InvalidStatusTransitionException,
    LeadService,
)

router = APIRouter(prefix="/leads", tags=["Leads"])


@router.post("", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    data: LeadCreate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> LeadResponse:
    data.organization_id = org_id
    service = LeadService(db)
    try:
        lead = await service.create_lead(data)
        return LeadResponse.model_validate(lead)
    except DuplicateEntityException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(e), "matched_entity_id": str(e.matched_entity_id)},
        )


@router.get("", response_model=PaginatedResponse[LeadResponse])
async def list_leads(
    status_filter: Optional[LeadStatus] = Query(None, alias="status", description="Filter by status"),
    lead_type: Optional[LeadType] = Query(None, description="Filter by lead type"),
    source_id: Optional[uuid.UUID] = Query(None, description="Filter by lead source"),
    minimum_score: Optional[int] = Query(None, ge=0, le=100, description="Minimum overall score"),
    maximum_score: Optional[int] = Query(None, ge=0, le=100, description="Maximum overall score"),
    search: Optional[str] = Query(None, description="Search title and summary"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> PaginatedResponse[LeadResponse]:
    service = LeadService(db)
    items, total, total_pages = await service.list_leads(
        org_id=org_id,
        status=status_filter.value if status_filter else None,
        lead_type=lead_type.value if lead_type else None,
        source_id=source_id,
        min_score=minimum_score,
        max_score=maximum_score,
        search=search,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        items=[LeadResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> LeadResponse:
    service = LeadService(db)
    try:
        lead = await service.get_lead(org_id, lead_id)
        return LeadResponse.model_validate(lead)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: uuid.UUID,
    data: LeadUpdate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> LeadResponse:
    service = LeadService(db)
    try:
        lead = await service.update_lead(org_id, lead_id, data)
        return LeadResponse.model_validate(lead)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> None:
    service = LeadService(db)
    try:
        await service.delete_lead(org_id, lead_id)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{lead_id}/status", response_model=LeadResponse)
async def update_lead_status(
    lead_id: uuid.UUID,
    update: LeadStatusUpdate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> LeadResponse:
    service = LeadService(db)
    try:
        lead = await service.transition_status(org_id, lead_id, update)
        return LeadResponse.model_validate(lead)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidStatusTransitionException as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))


@router.get("/{lead_id}/pipeline", response_model=List[PipelineEventResponse])
async def get_lead_pipeline_history(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> List[PipelineEventResponse]:
    service = LeadService(db)
    try:
        events = await service.get_pipeline_history(org_id, lead_id)
        return [PipelineEventResponse.model_validate(e) for e in events]
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{lead_id}/signals", response_model=List[LeadSignalResponse])
async def get_lead_signals(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> List[LeadSignalResponse]:
    service = LeadService(db)
    try:
        signals = await service.get_signals(org_id, lead_id)
        return [LeadSignalResponse.model_validate(s) for s in signals]
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{lead_id}/signals", response_model=LeadSignalResponse, status_code=status.HTTP_201_CREATED)
async def add_lead_signal(
    lead_id: uuid.UUID,
    data: LeadSignalCreate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> LeadSignalResponse:
    data.lead_id = lead_id
    service = LeadService(db)
    try:
        signal = await service.add_signal(org_id, data)
        return LeadSignalResponse.model_validate(signal)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
