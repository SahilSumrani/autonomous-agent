import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared_types.crm import MatchType
from services.api.app.models.crm import Company, Contact, Lead
from services.api.app.services.deduplication import DeduplicationEngine
from services.api.app.services.normalization import normalize_company_name, normalize_domain


@pytest.mark.asyncio
async def test_company_deduplication_by_domain(test_db_session: AsyncSession):
    org_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    company = Company(
        organization_id=org_id,
        name="Example Inc",
        normalized_name=normalize_company_name("Example Inc"),
        domain="example.com",
        normalized_domain=normalize_domain("example.com"),
    )
    test_db_session.add(company)
    await test_db_session.commit()

    # Search with variations of same domain
    result = await DeduplicationEngine.find_duplicate_company(
        test_db_session,
        org_id,
        name="Different Display Name",
        website_url="https://www.example.com/contact?ref=ad",
    )
    assert result.is_duplicate is True
    assert result.match_type == MatchType.DOMAIN
    assert result.matched_entity_id == company.id
    assert result.confidence == 1.0


@pytest.mark.asyncio
async def test_company_deduplication_prevents_accidental_merge(test_db_session: AsyncSession):
    org_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    company = Company(
        organization_id=org_id,
        name="ABC Technologies",
        normalized_name=normalize_company_name("ABC Technologies"),
        domain="abctechnologies.com",
        normalized_domain=normalize_domain("abctechnologies.com"),
    )
    test_db_session.add(company)
    await test_db_session.commit()

    # Similar but distinct name and different domain must NOT merge
    result = await DeduplicationEngine.find_duplicate_company(
        test_db_session,
        org_id,
        name="ABC Technology",
        domain="abctechnology.net",
    )
    assert result.is_duplicate is False
    assert result.match_type == MatchType.NONE


@pytest.mark.asyncio
async def test_contact_deduplication_by_verified_email(test_db_session: AsyncSession):
    org_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    contact = Contact(
        organization_id=org_id,
        first_name="Sahil",
        email="sahil@techverse.ai",
        email_verified=True,
    )
    test_db_session.add(contact)
    await test_db_session.commit()

    result = await DeduplicationEngine.find_duplicate_contact(
        test_db_session,
        org_id,
        email="  SAHIL@TECHVERSE.AI ",
    )
    assert result.is_duplicate is True
    assert result.match_type == MatchType.VERIFIED_EMAIL
    assert result.matched_entity_id == contact.id


@pytest.mark.asyncio
async def test_lead_deduplication_by_profile_url(test_db_session: AsyncSession):
    org_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    lead = Lead(
        organization_id=org_id,
        title="Prospect on Instagram",
        profile_url="https://instagram.com/prospect_brand",
    )
    test_db_session.add(lead)
    await test_db_session.commit()

    # Search with messy tracking parameters and http
    result = await DeduplicationEngine.find_duplicate_lead(
        test_db_session,
        org_id,
        profile_url="http://www.instagram.com/prospect_brand/?utm_source=ig",
    )
    assert result.is_duplicate is True
    assert result.match_type == MatchType.PROFILE_URL
    assert result.matched_entity_id == lead.id
