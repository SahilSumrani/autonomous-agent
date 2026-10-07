import math
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared_types.crm import (
    ActorType,
    LeadStatus,
    VALID_STATUS_TRANSITIONS,
)
from services.api.app.models.crm import (
    Company,
    Contact,
    Lead,
    LeadSignal,
    LeadSource,
    Organization,
    PipelineEvent,
)
from services.api.app.repositories.crm import (
    CompanyRepository,
    ContactRepository,
    LeadRepository,
    LeadSignalRepository,
    LeadSourceRepository,
    OrganizationRepository,
    PipelineEventRepository,
)
from services.api.app.schemas.crm import (
    CompanyCreate,
    CompanyUpdate,
    ContactCreate,
    ContactUpdate,
    LeadCreate,
    LeadSignalCreate,
    LeadStatusUpdate,
    LeadUpdate,
    PaginatedResponse,
)
from services.api.app.services.deduplication import DeduplicationEngine
from services.api.app.services.normalization import (
    normalize_company_name,
    normalize_domain,
    normalize_email,
    normalize_phone,
    normalize_profile_url,
    normalize_username,
)


class CRMServiceException(Exception):
    """Base exception for CRM business logic violations."""
    pass


class DuplicateEntityException(CRMServiceException):
    """Raised when an entity fails strict deduplication checks."""
    def __init__(self, message: str, matched_entity_id: Optional[uuid.UUID] = None):
        super().__init__(message)
        self.matched_entity_id = matched_entity_id


class InvalidStatusTransitionException(CRMServiceException):
    """Raised when an unauthorized or invalid status transition is requested."""
    pass


class EntityNotFoundException(CRMServiceException):
    """Raised when an entity does not exist or does not belong to the scoped organization."""
    pass


class CompanyService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CompanyRepository(session)

    async def create_company(self, data: CompanyCreate) -> Company:
        norm_name = normalize_company_name(data.name) or data.name.strip().lower()
        norm_domain = normalize_domain(data.domain) or normalize_domain(data.website_url)

        # Deduplication check
        dup = await DeduplicationEngine.find_duplicate_company(
            self.session,
            data.organization_id,
            name=data.name,
            domain=norm_domain,
            website_url=data.website_url,
        )
        if dup.is_duplicate:
            raise DuplicateEntityException(
                f"Duplicate company identified ({dup.details})",
                matched_entity_id=dup.matched_entity_id,
            )

        company = Company(
            organization_id=data.organization_id,
            name=data.name.strip(),
            normalized_name=norm_name,
            domain=data.domain.strip() if data.domain else norm_domain,
            normalized_domain=norm_domain,
            description=data.description,
            industry=data.industry,
            location=data.location,
            country=data.country,
            website_url=data.website_url,
            linkedin_url=normalize_profile_url(data.linkedin_url),
            instagram_url=normalize_profile_url(data.instagram_url),
            reddit_url=normalize_profile_url(data.reddit_url),
            status=data.status.value,
            metadata_json=data.metadata_json,
        )
        created = await self.repo.create(company)
        await self.session.commit()
        await self.session.refresh(created)
        return created

    async def get_company(self, org_id: uuid.UUID, company_id: uuid.UUID) -> Company:
        company = await self.repo.get_by_id(org_id, company_id)
        if not company:
            raise EntityNotFoundException(f"Company {company_id} not found")
        return company

    async def list_companies(
        self,
        org_id: uuid.UUID,
        search: Optional[str] = None,
        industry: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[Company], int, int]:
        items, total = await self.repo.list(org_id, search, industry, page, page_size)
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        return items, total, total_pages

    async def update_company(self, org_id: uuid.UUID, company_id: uuid.UUID, data: CompanyUpdate) -> Company:
        company = await self.get_company(org_id, company_id)

        update_dict = data.model_dump(exclude_unset=True)
        if "name" in update_dict and update_dict["name"]:
            company.name = update_dict["name"].strip()
            company.normalized_name = normalize_company_name(update_dict["name"]) or update_dict["name"].lower()
        if "domain" in update_dict:
            company.domain = update_dict["domain"]
            company.normalized_domain = normalize_domain(update_dict["domain"])
        if "website_url" in update_dict and not company.normalized_domain:
            company.normalized_domain = normalize_domain(update_dict["website_url"])

        for field in ["description", "industry", "location", "country", "website_url", "linkedin_url", "instagram_url", "reddit_url", "metadata_json"]:
            if field in update_dict:
                setattr(company, field, update_dict[field])
        if "status" in update_dict and update_dict["status"]:
            company.status = update_dict["status"].value

        await self.session.commit()
        await self.session.refresh(company)
        return company


class ContactService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ContactRepository(session)

    async def create_contact(self, data: ContactCreate) -> Contact:
        norm_email = normalize_email(data.email)
        norm_linkedin = normalize_profile_url(data.linkedin_url)
        norm_ig = normalize_username(data.instagram_username)
        norm_reddit = normalize_username(data.reddit_username)
        norm_phone = normalize_phone(data.phone)

        # Deduplication check
        dup = await DeduplicationEngine.find_duplicate_contact(
            self.session,
            data.organization_id,
            email=norm_email,
            linkedin_url=norm_linkedin,
            instagram_username=norm_ig,
            reddit_username=norm_reddit,
        )
        if dup.is_duplicate:
            raise DuplicateEntityException(
                f"Duplicate contact identified ({dup.details})",
                matched_entity_id=dup.matched_entity_id,
            )

        full_name = data.full_name
        if not full_name and (data.first_name or data.last_name):
            full_name = f"{data.first_name or ''} {data.last_name or ''}".strip()

        contact = Contact(
            organization_id=data.organization_id,
            company_id=data.company_id,
            first_name=data.first_name,
            last_name=data.last_name,
            full_name=full_name,
            job_title=data.job_title,
            email=norm_email,
            email_verified=data.email_verified,
            phone=norm_phone,
            instagram_username=norm_ig,
            instagram_url=data.instagram_url,
            reddit_username=norm_reddit,
            reddit_url=data.reddit_url,
            linkedin_url=norm_linkedin,
            location=data.location,
        )
        created = await self.repo.create(contact)
        await self.session.commit()
        await self.session.refresh(created)
        return created

    async def get_contact(self, org_id: uuid.UUID, contact_id: uuid.UUID) -> Contact:
        contact = await self.repo.get_by_id(org_id, contact_id)
        if not contact:
            raise EntityNotFoundException(f"Contact {contact_id} not found")
        return contact

    async def list_contacts(
        self,
        org_id: uuid.UUID,
        company_id: Optional[uuid.UUID] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[Contact], int, int]:
        items, total = await self.repo.list(org_id, company_id, search, page, page_size)
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        return items, total, total_pages

    async def update_contact(self, org_id: uuid.UUID, contact_id: uuid.UUID, data: ContactUpdate) -> Contact:
        contact = await self.get_contact(org_id, contact_id)
        update_dict = data.model_dump(exclude_unset=True)

        if "email" in update_dict and update_dict["email"]:
            contact.email = normalize_email(update_dict["email"])
        if "phone" in update_dict:
            contact.phone = normalize_phone(update_dict["phone"])
        if "instagram_username" in update_dict:
            contact.instagram_username = normalize_username(update_dict["instagram_username"])
        if "reddit_username" in update_dict:
            contact.reddit_username = normalize_username(update_dict["reddit_username"])
        if "linkedin_url" in update_dict:
            contact.linkedin_url = normalize_profile_url(update_dict["linkedin_url"])

        for field in ["first_name", "last_name", "full_name", "job_title", "email_verified", "instagram_url", "reddit_url", "location", "company_id"]:
            if field in update_dict:
                setattr(contact, field, update_dict[field])

        await self.session.commit()
        await self.session.refresh(contact)
        return contact


class LeadService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = LeadRepository(session)
        self.signal_repo = LeadSignalRepository(session)
        self.event_repo = PipelineEventRepository(session)

    async def create_lead(self, data: LeadCreate) -> Lead:
        norm_profile = normalize_profile_url(data.profile_url)

        # Deduplication check
        dup = await DeduplicationEngine.find_duplicate_lead(
            self.session,
            data.organization_id,
            profile_url=norm_profile,
            company_id=data.company_id,
            contact_id=data.contact_id,
        )
        if dup.is_duplicate:
            raise DuplicateEntityException(
                f"Duplicate lead detected ({dup.details})",
                matched_entity_id=dup.matched_entity_id,
            )

        lead = Lead(
            organization_id=data.organization_id,
            company_id=data.company_id,
            contact_id=data.contact_id,
            source_id=data.source_id,
            status=data.status.value,
            lead_type=data.lead_type.value,
            source_url=data.source_url,
            profile_url=norm_profile,
            content_url=data.content_url,
            title=data.title,
            summary=data.summary,
            intent_score=data.intent_score,
            qualification_score=data.qualification_score,
            overall_score=data.overall_score,
            recommended_service=data.recommended_service,
        )
        created = await self.repo.create(lead)

        # Record initial pipeline event
        event = PipelineEvent(
            lead_id=created.id,
            old_status=None,
            new_status=created.status,
            actor_type=ActorType.SYSTEM.value,
            reason="Lead created",
        )
        await self.event_repo.create(event)

        await self.session.commit()
        await self.session.refresh(created)
        return created

    async def get_lead(self, org_id: uuid.UUID, lead_id: uuid.UUID) -> Lead:
        lead = await self.repo.get_by_id(org_id, lead_id)
        if not lead:
            raise EntityNotFoundException(f"Lead {lead_id} not found")
        return lead

    async def list_leads(
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
    ) -> Tuple[List[Lead], int, int]:
        items, total = await self.repo.list(
            org_id=org_id,
            status=status,
            lead_type=lead_type,
            source_id=source_id,
            min_score=min_score,
            max_score=max_score,
            search=search,
            page=page,
            page_size=page_size,
        )
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        return items, total, total_pages

    async def update_lead(self, org_id: uuid.UUID, lead_id: uuid.UUID, data: LeadUpdate) -> Lead:
        lead = await self.get_lead(org_id, lead_id)
        update_dict = data.model_dump(exclude_unset=True)

        if "lead_type" in update_dict and update_dict["lead_type"]:
            lead.lead_type = update_dict["lead_type"].value
        if "profile_url" in update_dict:
            lead.profile_url = normalize_profile_url(update_dict["profile_url"])

        for field in [
            "title", "summary", "company_id", "contact_id", "source_id", "source_url",
            "content_url", "intent_score", "qualification_score", "overall_score",
            "recommended_service"
        ]:
            if field in update_dict and update_dict[field] is not None:
                setattr(lead, field, update_dict[field])

        lead.last_seen_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(lead)
        return lead

    async def delete_lead(self, org_id: uuid.UUID, lead_id: uuid.UUID) -> bool:
        lead = await self.get_lead(org_id, lead_id)
        res = await self.repo.delete(org_id, lead.id)
        await self.session.commit()
        return res

    async def transition_status(
        self,
        org_id: uuid.UUID,
        lead_id: uuid.UUID,
        update: LeadStatusUpdate,
    ) -> Lead:
        lead = await self.get_lead(org_id, lead_id)
        current_status = LeadStatus(lead.status)
        target_status = update.new_status

        if current_status == target_status:
            return lead

        allowed_targets = VALID_STATUS_TRANSITIONS.get(current_status, set())
        if target_status not in allowed_targets:
            raise InvalidStatusTransitionException(
                f"Invalid status transition from {current_status.value} to {target_status.value}. "
                f"Permitted transitions: {[s.value for s in allowed_targets]}"
            )

        old_status = lead.status
        lead.status = target_status.value
        lead.last_seen_at = datetime.now(timezone.utc)

        event = PipelineEvent(
            lead_id=lead.id,
            old_status=old_status,
            new_status=target_status.value,
            actor_type=update.actor_type.value,
            actor_id=update.actor_id,
            reason=update.reason,
            metadata_json=update.metadata_json,
        )
        await self.event_repo.create(event)

        await self.session.commit()
        await self.session.refresh(lead)
        return lead

    async def add_signal(self, org_id: uuid.UUID, data: LeadSignalCreate) -> LeadSignal:
        lead = await self.get_lead(org_id, data.lead_id)
        signal = LeadSignal(
            lead_id=lead.id,
            signal_type=data.signal_type.value,
            confidence=data.confidence,
            evidence=data.evidence,
            source_url=data.source_url,
            detected_at=data.detected_at or datetime.now(timezone.utc),
        )
        created = await self.signal_repo.create(signal)
        await self.session.commit()
        await self.session.refresh(created)
        return created

    async def get_signals(self, org_id: uuid.UUID, lead_id: uuid.UUID) -> List[LeadSignal]:
        # Validate lead belongs to org
        await self.get_lead(org_id, lead_id)
        return await self.signal_repo.list_by_lead(lead_id)

    async def get_pipeline_history(self, org_id: uuid.UUID, lead_id: uuid.UUID) -> List[PipelineEvent]:
        # Validate lead belongs to org
        await self.get_lead(org_id, lead_id)
        return await self.event_repo.list_by_lead(lead_id)
