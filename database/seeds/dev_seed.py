import asyncio
import logging
import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.core.database import AsyncSessionLocal
from services.api.app.models.crm import Organization, User
from packages.shared_types.crm import UserRole

logger = logging.getLogger("techverse.database.seeds")

DEV_ORGANIZATION_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEV_ORGANIZATION_NAME = "TechVerse AI Development"
DEV_ORGANIZATION_SLUG = "techverse-dev"


async def seed_development_organization(session: Optional[AsyncSession] = None) -> Organization:
    """
    Idempotently bootstrap the default development organization.
    Uses deterministic UUID 00000000-0000-0000-0000-000000000001.
    """
    if session is not None:
        return await _ensure_dev_org(session)

    async with AsyncSessionLocal() as db_session:
        return await _ensure_dev_org(db_session)


async def _ensure_dev_org(session: AsyncSession) -> Organization:
    # 1. Check if organization already exists by ID or Slug
    stmt = select(Organization).where(
        (Organization.id == DEV_ORGANIZATION_ID) | (Organization.slug == DEV_ORGANIZATION_SLUG)
    )
    res = await session.execute(stmt)
    org = res.scalar_one_or_none()

    if org:
        logger.info(
            "Development organization already exists: %s (%s)",
            org.id,
            org.slug,
        )
        return org

    # 2. Insert organization idempotently
    org = Organization(
        id=DEV_ORGANIZATION_ID,
        name=DEV_ORGANIZATION_NAME,
        slug=DEV_ORGANIZATION_SLUG,
    )
    session.add(org)
    try:
        await session.commit()
        await session.refresh(org)
        logger.info(
            "Created development organization: %s (%s)",
            org.id,
            org.slug,
        )
    except IntegrityError:
        await session.rollback()
        # Concurrency safety: fetch the organization created in parallel
        stmt = select(Organization).where(Organization.id == DEV_ORGANIZATION_ID)
        res = await session.execute(stmt)
        org = res.scalar_one()

    return org


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed_development_organization())
