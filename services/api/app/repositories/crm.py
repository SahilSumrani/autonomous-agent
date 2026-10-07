import uuid
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.models.crm import (
    Company,
    Contact,
    Lead,
    LeadSignal,
    LeadSource,
    Organization,
    PipelineEvent,
    User,
)


class OrganizationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, organization: Organization) -> Organization:
        self.session.add(organization)
        await self.session.flush()
        return organization

    async def get_by_id(self, org_id: uuid.UUID) -> Optional[Organization]:
        stmt = select(Organization).where(Organization.id == org_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[Organization]:
        stmt = select(Organization).where(Organization.slug == slug)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user

    async def get_by_id(self, org_id: uuid.UUID, user_id: uuid.UUID) -> Optional[User]:
        stmt = select(User).where(User.organization_id == org_id, User.id == user_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_email(self, org_id: uuid.UUID, email: str) -> Optional[User]:
        stmt = select(User).where(User.organization_id == org_id, User.email == email)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()


class CompanyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, company: Company) -> Company:
        self.session.add(company)
        await self.session.flush()
        return company

    async def get_by_id(self, org_id: uuid.UUID, company_id: uuid.UUID) -> Optional[Company]:
        stmt = select(Company).where(Company.organization_id == org_id, Company.id == company_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_normalized_domain(self, org_id: uuid.UUID, domain: str) -> Optional[Company]:
        stmt = select(Company).where(Company.organization_id == org_id, Company.normalized_domain == domain)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list(
        self,
        org_id: uuid.UUID,
        search: Optional[str] = None,
        industry: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[Company], int]:
        query = select(Company).where(Company.organization_id == org_id)

        if search:
            query = query.where(Company.name.ilike(f"%{search}%") | Company.domain.ilike(f"%{search}%"))
        if industry:
            query = query.where(Company.industry == industry)

        total_stmt = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(total_stmt)).scalar_one()

        offset = (page - 1) * page_size
        items_stmt = query.order_by(desc(Company.created_at)).offset(offset).limit(page_size)
        items = (await self.session.execute(items_stmt)).scalars().all()

        return list(items), total

    async def delete(self, org_id: uuid.UUID, company_id: uuid.UUID) -> bool:
        company = await self.get_by_id(org_id, company_id)
        if not company:
            return False
        await self.session.delete(company)
        await self.session.flush()
        return True


class ContactRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, contact: Contact) -> Contact:
        self.session.add(contact)
        await self.session.flush()
        return contact

    async def get_by_id(self, org_id: uuid.UUID, contact_id: uuid.UUID) -> Optional[Contact]:
        stmt = select(Contact).where(Contact.organization_id == org_id, Contact.id == contact_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_email(self, org_id: uuid.UUID, email: str) -> Optional[Contact]:
        stmt = select(Contact).where(Contact.organization_id == org_id, Contact.email == email)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list(
        self,
        org_id: uuid.UUID,
        company_id: Optional[uuid.UUID] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[Contact], int]:
        query = select(Contact).where(Contact.organization_id == org_id)

        if company_id:
            query = query.where(Contact.company_id == company_id)
        if search:
            query = query.where(
                Contact.full_name.ilike(f"%{search}%")
                | Contact.email.ilike(f"%{search}%")
                | Contact.instagram_username.ilike(f"%{search}%")
            )

        total_stmt = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(total_stmt)).scalar_one()

        offset = (page - 1) * page_size
        items_stmt = query.order_by(desc(Contact.created_at)).offset(offset).limit(page_size)
        items = (await self.session.execute(items_stmt)).scalars().all()

        return list(items), total

    async def delete(self, org_id: uuid.UUID, contact_id: uuid.UUID) -> bool:
        contact = await self.get_by_id(org_id, contact_id)
        if not contact:
            return False
        await self.session.delete(contact)
        await self.session.flush()
        return True


class LeadSourceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, source: LeadSource) -> LeadSource:
        self.session.add(source)
        await self.session.flush()
        return source

    async def get_by_id(self, org_id: uuid.UUID, source_id: uuid.UUID) -> Optional[LeadSource]:
        stmt = select(LeadSource).where(LeadSource.organization_id == org_id, LeadSource.id == source_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()


class LeadRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, lead: Lead) -> Lead:
        self.session.add(lead)
        await self.session.flush()
        return lead

    async def get_by_id(self, org_id: uuid.UUID, lead_id: uuid.UUID) -> Optional[Lead]:
        stmt = select(Lead).where(Lead.organization_id == org_id, Lead.id == lead_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_profile_url(self, org_id: uuid.UUID, profile_url: str) -> Optional[Lead]:
        stmt = select(Lead).where(Lead.organization_id == org_id, Lead.profile_url == profile_url)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list(
        self,
        org_id: uuid.UUID,
        status: Optional[str] = None,
        lead_type: Optional[str] = None,
        source_id: Optional[uuid.UUID] = None,
        min_score: Optional[int] = None,
        max_score: Optional[int] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[Lead], int]:
        query = select(Lead).where(Lead.organization_id == org_id)

        if status:
            query = query.where(Lead.status == status)
        if lead_type:
            query = query.where(Lead.lead_type == lead_type)
        if source_id:
            query = query.where(Lead.source_id == source_id)
        if min_score is not None:
            query = query.where(Lead.overall_score >= min_score)
        if max_score is not None:
            query = query.where(Lead.overall_score <= max_score)
        if search:
            query = query.where(
                Lead.title.ilike(f"%{search}%") | Lead.summary.ilike(f"%{search}%")
            )

        total_stmt = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(total_stmt)).scalar_one()

        offset = (page - 1) * page_size
        items_stmt = query.order_by(desc(Lead.created_at)).offset(offset).limit(page_size)
        items = (await self.session.execute(items_stmt)).scalars().all()

        return list(items), total

    async def delete(self, org_id: uuid.UUID, lead_id: uuid.UUID) -> bool:
        lead = await self.get_by_id(org_id, lead_id)
        if not lead:
            return False
        await self.session.delete(lead)
        await self.session.flush()
        return True


class LeadSignalRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, signal: LeadSignal) -> LeadSignal:
        self.session.add(signal)
        await self.session.flush()
        return signal

    async def list_by_lead(self, lead_id: uuid.UUID) -> List[LeadSignal]:
        stmt = select(LeadSignal).where(LeadSignal.lead_id == lead_id).order_by(desc(LeadSignal.detected_at))
        res = await self.session.execute(stmt)
        return list(res.scalars().all())


class PipelineEventRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, event: PipelineEvent) -> PipelineEvent:
        self.session.add(event)
        await self.session.flush()
        return event

    async def list_by_lead(self, lead_id: uuid.UUID) -> List[PipelineEvent]:
        stmt = select(PipelineEvent).where(PipelineEvent.lead_id == lead_id).order_by(desc(PipelineEvent.created_at))
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
