import uuid
from typing import Optional
from fastapi import Header, HTTPException, status

# Default development organization UUID for local-first testing
DEFAULT_DEV_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def get_current_org_id(
    x_organization_id: Optional[str] = Header(None, alias="X-Organization-ID")
) -> uuid.UUID:
    """
    Extract and validate the active organization ID from request headers.
    Enforces multi-tenant data isolation. Defaults to standard dev workspace if unset.
    """
    if not x_organization_id:
        return DEFAULT_DEV_ORG_ID

    try:
        return uuid.UUID(x_organization_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid X-Organization-ID UUID header",
        )
