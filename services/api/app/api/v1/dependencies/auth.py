import uuid
from typing import Optional
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from packages.config.settings import settings
from services.api.app.core.database import get_db
from services.api.app.repositories.crm import OrganizationRepository

# Default development organization UUID for local-first testing
DEFAULT_DEV_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def get_current_org_id(
    x_organization_id: Optional[str] = Header(None, alias="X-Organization-ID"),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    """
    Extract and validate the active organization ID from request headers.
    Enforces multi-tenant data isolation.
    - Production: Requires explicit X-Organization-ID header referencing an existing organization.
    - Development/Test: Defaults to DEFAULT_DEV_ORG_ID only when that organization exists in the database.
    """
    if not x_organization_id:
        if settings.ENVIRONMENT == "production":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required X-Organization-ID header in production environment",
            )
        # Development / test fallback: verify development organization exists
        org_repo = OrganizationRepository(db)
        dev_org = await org_repo.get_by_id(DEFAULT_DEV_ORG_ID)
        if not dev_org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Development organization {DEFAULT_DEV_ORG_ID} not found or uninitialized",
            )
        return DEFAULT_DEV_ORG_ID

    try:
        org_id = uuid.UUID(x_organization_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid X-Organization-ID UUID header",
        )

    org_repo = OrganizationRepository(db)
    org = await org_repo.get_by_id(org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization {org_id} not found",
        )

    return org_id
