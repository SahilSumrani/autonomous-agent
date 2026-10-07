import uuid
from typing import List, Optional
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from services.api.app.models.research import WebsitePageResearch, WebsiteResearch


class WebsiteResearchRepository:
    """Repository handling CRUD persistence for website research audits and pages."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_research(self, research: WebsiteResearch) -> WebsiteResearch:
        self.session.add(research)
        await self.session.flush()
        await self.session.refresh(research)
        return research

    async def get_by_id(self, research_id: uuid.UUID, org_id: uuid.UUID) -> Optional[WebsiteResearch]:
        query = (
            select(WebsiteResearch)
            .where(
                WebsiteResearch.id == research_id,
                WebsiteResearch.organization_id == org_id,
            )
            .options(selectinload(WebsiteResearch.pages))
        )
        res = await self.session.execute(query)
        return res.scalar_one_or_none()

    async def get_latest_for_lead(self, lead_id: uuid.UUID, org_id: uuid.UUID) -> Optional[WebsiteResearch]:
        query = (
            select(WebsiteResearch)
            .where(
                WebsiteResearch.lead_id == lead_id,
                WebsiteResearch.organization_id == org_id,
            )
            .order_by(desc(WebsiteResearch.created_at))
            .options(selectinload(WebsiteResearch.pages))
            .limit(1)
        )
        res = await self.session.execute(query)
        return res.scalar_one_or_none()

    async def list_history_for_lead(self, lead_id: uuid.UUID, org_id: uuid.UUID) -> List[WebsiteResearch]:
        query = (
            select(WebsiteResearch)
            .where(
                WebsiteResearch.lead_id == lead_id,
                WebsiteResearch.organization_id == org_id,
            )
            .order_by(desc(WebsiteResearch.created_at))
        )
        res = await self.session.execute(query)
        return list(res.scalars().all())

    async def add_page_research(self, page: WebsitePageResearch) -> WebsitePageResearch:
        self.session.add(page)
        await self.session.flush()
        await self.session.refresh(page)
        return page

    async def get_pages_for_research(
        self, research_id: uuid.UUID, org_id: uuid.UUID
    ) -> List[WebsitePageResearch]:
        query = (
            select(WebsitePageResearch)
            .where(
                WebsitePageResearch.research_id == research_id,
                WebsitePageResearch.organization_id == org_id,
            )
            .order_by(WebsitePageResearch.created_at)
        )
        res = await self.session.execute(query)
        return list(res.scalars().all())
