import uuid
from typing import Optional
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared_types.crm import MatchType
from services.api.app.models.crm import Company, Contact, Lead
from services.api.app.services.normalization import (
    normalize_company_name,
    normalize_domain,
    normalize_email,
    normalize_profile_url,
)


class DeduplicationResult(BaseModel):
    """Structured result returned by the deduplication engine."""
    is_duplicate: bool
    matched_entity_id: Optional[uuid.UUID] = None
    match_type: MatchType = MatchType.NONE
    confidence: float = 0.0
    details: Optional[str] = None


class DeduplicationEngine:
    """
    Deterministic deduplication engine enforcing hierarchical matching:
    1. Exact normalized domain (Confidence: 1.0)
    2. Exact normalized profile URL (Confidence: 0.95)
    3. Verified email (Confidence: 0.90)
    4. Exact normalized company name (Confidence: 0.75 - exact match only)
    """

    @classmethod
    async def find_duplicate_company(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        name: str,
        domain: Optional[str] = None,
        website_url: Optional[str] = None,
    ) -> DeduplicationResult:
        """Find existing company within organization matching strict criteria."""
        norm_domain = normalize_domain(domain) or normalize_domain(website_url)
        norm_name = normalize_company_name(name)

        # 1. Exact normalized domain match
        if norm_domain:
            stmt = select(Company).where(
                Company.organization_id == organization_id,
                Company.normalized_domain == norm_domain,
            ).limit(1)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                return DeduplicationResult(
                    is_duplicate=True,
                    matched_entity_id=existing.id,
                    match_type=MatchType.DOMAIN,
                    confidence=1.0,
                    details=f"Exact domain match: {norm_domain}",
                )

        # 2. Exact normalized company name match
        if norm_name:
            stmt = select(Company).where(
                Company.organization_id == organization_id,
                Company.normalized_name == norm_name,
            ).limit(1)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                return DeduplicationResult(
                    is_duplicate=True,
                    matched_entity_id=existing.id,
                    match_type=MatchType.COMPANY_NAME,
                    confidence=0.75,
                    details=f"Exact normalized company name match: {norm_name}",
                )

        return DeduplicationResult(is_duplicate=False)

    @classmethod
    async def find_duplicate_contact(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        email: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        instagram_username: Optional[str] = None,
        reddit_username: Optional[str] = None,
    ) -> DeduplicationResult:
        """Find existing contact within organization matching verified email or social handles."""
        norm_email = normalize_email(email)
        norm_linkedin = normalize_profile_url(linkedin_url)

        # 1. Verified / exact normalized email
        if norm_email:
            stmt = select(Contact).where(
                Contact.organization_id == organization_id,
                Contact.email == norm_email,
            ).limit(1)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                confidence = 1.0 if existing.email_verified else 0.90
                return DeduplicationResult(
                    is_duplicate=True,
                    matched_entity_id=existing.id,
                    match_type=MatchType.VERIFIED_EMAIL,
                    confidence=confidence,
                    details=f"Email match: {norm_email}",
                )

        # 2. LinkedIn URL
        if norm_linkedin:
            stmt = select(Contact).where(
                Contact.organization_id == organization_id,
                Contact.linkedin_url == norm_linkedin,
            ).limit(1)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                return DeduplicationResult(
                    is_duplicate=True,
                    matched_entity_id=existing.id,
                    match_type=MatchType.PROFILE_URL,
                    confidence=0.95,
                    details=f"LinkedIn profile match: {norm_linkedin}",
                )

        return DeduplicationResult(is_duplicate=False)

    @classmethod
    async def find_duplicate_lead(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        profile_url: Optional[str] = None,
        company_id: Optional[uuid.UUID] = None,
        contact_id: Optional[uuid.UUID] = None,
    ) -> DeduplicationResult:
        """Find existing lead within organization by profile URL or company/contact link."""
        norm_profile = normalize_profile_url(profile_url)

        # 1. Exact normalized profile URL
        if norm_profile:
            stmt = select(Lead).where(
                Lead.organization_id == organization_id,
                Lead.profile_url == norm_profile,
            ).limit(1)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                return DeduplicationResult(
                    is_duplicate=True,
                    matched_entity_id=existing.id,
                    match_type=MatchType.PROFILE_URL,
                    confidence=0.95,
                    details=f"Lead profile URL match: {norm_profile}",
                )

        # 2. Existing active lead with identical company
        if company_id:
            stmt = select(Lead).where(
                Lead.organization_id == organization_id,
                Lead.company_id == company_id,
            ).limit(1)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                return DeduplicationResult(
                    is_duplicate=True,
                    matched_entity_id=existing.id,
                    match_type=MatchType.DOMAIN,
                    confidence=0.85,
                    details=f"Lead already exists for company ID: {company_id}",
                )

        # 3. Existing active lead with identical contact
        if contact_id:
            stmt = select(Lead).where(
                Lead.organization_id == organization_id,
                Lead.contact_id == contact_id,
            ).limit(1)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                return DeduplicationResult(
                    is_duplicate=True,
                    matched_entity_id=existing.id,
                    match_type=MatchType.VERIFIED_EMAIL,
                    confidence=0.80,
                    details=f"Lead already exists for contact ID: {contact_id}",
                )

        return DeduplicationResult(is_duplicate=False)
