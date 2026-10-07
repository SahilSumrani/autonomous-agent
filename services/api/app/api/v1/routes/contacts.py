import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.api.v1.dependencies.auth import get_current_org_id
from services.api.app.core.database import get_db
from services.api.app.schemas.crm import (
    ContactCreate,
    ContactResponse,
    ContactUpdate,
    PaginatedResponse,
)
from services.api.app.services.crm_service import (
    ContactService,
    DuplicateEntityException,
    EntityNotFoundException,
)

router = APIRouter(prefix="/contacts", tags=["Contacts"])


@router.post("", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def create_contact(
    data: ContactCreate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> ContactResponse:
    data.organization_id = org_id
    service = ContactService(db)
    try:
        contact = await service.create_contact(data)
        return ContactResponse.model_validate(contact)
    except DuplicateEntityException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(e), "matched_entity_id": str(e.matched_entity_id)},
        )


@router.get("", response_model=PaginatedResponse[ContactResponse])
async def list_contacts(
    company_id: Optional[uuid.UUID] = Query(None, description="Filter by company"),
    search: Optional[str] = Query(None, description="Search by name, email, or username"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> PaginatedResponse[ContactResponse]:
    service = ContactService(db)
    items, total, total_pages = await service.list_contacts(
        org_id=org_id,
        company_id=company_id,
        search=search,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        items=[ContactResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@router.get("/{contact_id}", response_model=ContactResponse)
async def get_contact(
    contact_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> ContactResponse:
    service = ContactService(db)
    try:
        contact = await service.get_contact(org_id, contact_id)
        return ContactResponse.model_validate(contact)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact_id: uuid.UUID,
    data: ContactUpdate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> ContactResponse:
    service = ContactService(db)
    try:
        contact = await service.update_contact(org_id, contact_id, data)
        return ContactResponse.model_validate(contact)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
