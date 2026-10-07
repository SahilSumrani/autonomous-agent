import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.api.v1.dependencies.auth import get_current_org_id
from services.api.app.core.database import get_db
from services.api.app.schemas.crm import (
    CompanyCreate,
    CompanyResponse,
    CompanyUpdate,
    PaginatedResponse,
)
from services.api.app.services.crm_service import (
    CompanyService,
    DuplicateEntityException,
    EntityNotFoundException,
)

router = APIRouter(prefix="/companies", tags=["Companies"])


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    data: CompanyCreate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> CompanyResponse:
    data.organization_id = org_id
    service = CompanyService(db)
    try:
        company = await service.create_company(data)
        return CompanyResponse.model_validate(company)
    except DuplicateEntityException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(e), "matched_entity_id": str(e.matched_entity_id)},
        )


@router.get("", response_model=PaginatedResponse[CompanyResponse])
async def list_companies(
    search: Optional[str] = Query(None, description="Search by name or domain"),
    industry: Optional[str] = Query(None, description="Filter by industry"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> PaginatedResponse[CompanyResponse]:
    service = CompanyService(db)
    items, total, total_pages = await service.list_companies(
        org_id=org_id,
        search=search,
        industry=industry,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        items=[CompanyResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> CompanyResponse:
    service = CompanyService(db)
    try:
        company = await service.get_company(org_id, company_id)
        return CompanyResponse.model_validate(company)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: uuid.UUID,
    data: CompanyUpdate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> CompanyResponse:
    service = CompanyService(db)
    try:
        company = await service.update_company(org_id, company_id, data)
        return CompanyResponse.model_validate(company)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
