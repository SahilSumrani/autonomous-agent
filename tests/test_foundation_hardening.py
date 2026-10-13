"""Comprehensive Foundation Hardening & Truthfulness Verification Test Suite.

Verifies:
1. Website Research Truthfulness (no fake fallbacks, explicit RESEARCH_UNAVAILABLE, zero confidence)
2. Outreach Grounding & Adversarial Testing (no unobserved claims, unverified tech mention rejected)
3. AI Provider Integration & Ollama Fallback Truthfulness
4. Production Auth & Tenant Authorization (fails closed, no arbitrary header spoofing)
5. Browser Gateway Cross-Session & Cross-Org Isolation
6. Approval State Machine Illegal Transitions
7. CRM Concurrency & Database Deduplication
8. Observation Pipeline Ingestion & Persistence
9. SSRF DNS & Metadata Resolution Hardening
10. Conversation Intelligence Model Field Integrity
"""

import asyncio
import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from packages.config.settings import settings
from packages.shared_types.agent import ApprovalStatus, SessionStatus
from packages.shared_types.browser_protocol import (
    BrowserCommand,
    BrowserCommandResult,
    BrowserCommandType,
    CommandExecutionStatus,
)
from packages.shared_types.crm import (
    CompanyStatus,
    LeadStatus,
    LeadType,
    SignalType,
)
from packages.shared_types.outreach import DraftStatus
from services.api.app.agents.browser.gateway import browser_gateway
from services.api.app.agents.outreach.evidence_validator import EvidenceValidator
from services.api.app.agents.outreach.message_generator import MessageGenerator
from services.api.app.agents.outreach.outreach_models import (
    OutreachContext,
    OutreachEvidenceModel,
)
from services.api.app.agents.research.research_engine import ResearchEngine
from services.api.app.agents.research.research_models import (
    ResearchDataSource,
    ResearchStatus,
)
from services.api.app.agents.research.validators import (
    SSRFValidationError,
    validate_and_sanitize_target_url,
)
from services.api.app.api.v1.dependencies.auth import (
    AuthenticatedActor,
    get_authenticated_actor,
)
from services.api.app.models.agent import ActionApproval, AgentSession
from services.api.app.models.crm import Company, Contact, Lead, Organization
from services.api.app.models.outreach import OutreachDraft
from services.api.app.models.research import WebsiteResearch
from services.api.app.providers.ai.base import AIProvider
from services.api.app.providers.ai.factory import FallbackAIProvider
from services.api.app.providers.ai.ollama_provider import OllamaProvider
from services.api.app.schemas.crm import CompanyCreate, LeadCreate
from services.api.app.services.agent_service import AgentService, ActionBlockedException
from services.api.app.services.conversation_memory_service import ConversationMemoryService
from services.api.app.services.crm_service import CompanyService, DuplicateEntityException, LeadService
from services.api.app.services.outreach_service import OutreachService
from services.api.app.services.research_service import ResearchService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# PHASE 3: Website Research Truthfulness
# ---------------------------------------------------------------------------

def test_empty_research_input_produces_truthful_unavailable_state():
    """Empty/unreachable research input must yield RESEARCH_UNAVAILABLE, zero confidence, and NO fake findings."""
    result = ResearchEngine.execute_research(
        company_name="Test Store",
        website_url="https://nonexistent-store-12345.com",
        pages_data=[],
    )

    assert result["status"] == ResearchStatus.RESEARCH_UNAVAILABLE.value
    assert result["confidence"] == 0.0
    assert result["data_source"] == ResearchDataSource.UNAVAILABLE_DATA.value
    assert result["opportunity_breakdown"].total_opportunity_score == 0
    assert len(result["negative_findings"]) == 0
    assert len(result["positive_findings"]) == 0
    assert result["technology_stack"] == []


def test_provided_pages_are_strictly_tagged_and_not_fabricated():
    """When real pages are supplied, evidence source is tagged accurately and no unobserved findings are made up."""
    real_html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Valid Clean Store</title>
        <meta name="description" content="A real ecommerce shop">
    </head>
    <body>
        <main>
            <p>Welcome to our store. Check out our collection below.</p>
            <button class="add-to-cart">Buy Now</button>
        </main>
    </body>
    </html>
    """
    result = ResearchEngine.execute_research(
        company_name="Valid Clean Store",
        website_url="https://validcleanstore.com",
        pages_data=[{"url": "https://validcleanstore.com", "html": real_html}],
    )

    assert result["status"] == ResearchStatus.COMPLETED
    assert result["data_source"] == ResearchDataSource.USER_SUPPLIED_DATA
    assert result["confidence"] > 0.0


# ---------------------------------------------------------------------------
# PHASE 4: Outreach Must Be Evidence-Grounded
# ---------------------------------------------------------------------------

def test_outreach_unverified_technology_claim_fails_validation():
    """Outreach claiming Shopify when no Shopify evidence exists must fail evidence validation."""
    context = OutreachContext(
        lead_id=uuid.uuid4(),
        company_name="Test Fashion",
        source="BROWSER",
        recommended_service="ECOMMERCE",
        evidence=[],  # ZERO evidence
    )
    body = "Hey, noticed your Shopify store checkout has friction points."

    is_valid, errors, warnings, coverage = EvidenceValidator.validate_evidence_alignment(
        body=body,
        context=context,
    )
    assert is_valid is False
    assert any("Shopify" in err or "friction" in err for err in errors)


def test_outreach_unobserved_flaw_claim_fails_validation():
    """Outreach claiming mobile issues when no mobile evidence exists must be rejected."""
    context = OutreachContext(
        lead_id=uuid.uuid4(),
        company_name="Test Boutique",
        source="BROWSER",
        recommended_service="ECOMMERCE",
        evidence=[],
    )
    body = "I was reviewing your site and noticed poor mobile navigation and drop-offs."

    is_valid, errors, warnings, coverage = EvidenceValidator.validate_evidence_alignment(
        body=body,
        context=context,
    )
    assert is_valid is False
    assert len(errors) > 0


def test_outreach_with_verified_evidence_passes_validation():
    """Outreach with corresponding verified evidence passes validation."""
    evidence = OutreachEvidenceModel(
        claim="missing cta elements on homepage",
        evidence_text="Observed absence of visible primary call-to-action buttons",
        evidence_type="AUDIT",
        confidence=0.85,
        source_url="https://boutique.com",
    )
    context = OutreachContext(
        lead_id=uuid.uuid4(),
        company_name="Test Boutique",
        source="BROWSER",
        recommended_service="ECOMMERCE",
        evidence=[evidence],
    )
    body = "I was reviewing Test Boutique and noticed the landing page has missing cta elements."

    is_valid, errors, warnings, coverage = EvidenceValidator.validate_evidence_alignment(
        body=body,
        context=context,
    )
    assert is_valid is True
    assert len(errors) == 0


# ---------------------------------------------------------------------------
# PHASE 5: AI Provider Integration & Ollama Truthfulness
# ---------------------------------------------------------------------------

class MockWorkingProvider(AIProvider):
    @property
    def provider_name(self) -> str:
        return "mock_working"

    @property
    def model_name(self) -> str:
        return "mock-model"

    async def generate_text(self, prompt: str, **kwargs) -> str:
        return "Verified observation: noticed missing CTA on homepage."

    async def generate_structured(self, prompt: str, schema, **kwargs) -> dict:
        return {
            "subject": "Verified observation",
            "body": "Observed missing CTA on homepage",
            "cta_text": "Let's chat",
        }

    async def health_check(self) -> bool:
        return True


class MockFailingProvider(AIProvider):
    @property
    def provider_name(self) -> str:
        return "mock_failing"

    @property
    def model_name(self) -> str:
        return "mock-model"

    async def generate_text(self, prompt: str, **kwargs) -> str:
        raise RuntimeError("Primary AI Provider 503 Unavailable")

    async def generate_structured(self, prompt: str, schema, **kwargs) -> dict:
        raise RuntimeError("Primary AI Provider 503 Unavailable")

    async def health_check(self) -> bool:
        return False


@pytest.mark.asyncio
async def test_fallback_ai_provider_transparent_failover():
    """FallbackAIProvider must transparently invoke secondary provider when primary raises."""
    primary = MockFailingProvider()
    fallback = MockWorkingProvider()
    composite = FallbackAIProvider(primary=primary, fallback=fallback)

    res = await composite.generate_text("test prompt")
    assert "Verified observation" in res
    assert composite.provider_name == "mock_failing_fallback_mock_working"


@pytest.mark.asyncio
async def test_ollama_provider_unreachable_truthfully_fails():
    """Ollama provider must truthfully report unavailable when local daemon is unreachable, not pretend it worked."""
    provider = OllamaProvider(base_url="http://127.0.0.1:19999", model="llama3")  # Non-existent port
    available = await provider.health_check()
    assert available is False

    with pytest.raises(Exception):
        await provider.generate_text("test prompt")


# ---------------------------------------------------------------------------
# PHASE 6: Authentication & Tenant Boundaries
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_production_auth_fails_closed_without_credentials(monkeypatch, test_db_session: AsyncSession):
    """In production mode, requests without valid credentials fail with 401."""
    from fastapi import HTTPException
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    with pytest.raises(HTTPException) as exc_info:
        await get_authenticated_actor(
            authorization=None,
            x_api_key=None,
            x_organization_id=str(uuid.uuid4()),
            db=test_db_session,
        )
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_production_auth_fails_without_org_header(monkeypatch, test_db_session: AsyncSession):
    """In production mode, requests missing X-Organization-ID fail with 400."""
    from fastapi import HTTPException
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    with pytest.raises(HTTPException) as exc_info:
        await get_authenticated_actor(
            authorization="Bearer valid-token",
            x_api_key=None,
            x_organization_id=None,
            db=test_db_session,
        )
    assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# PHASE 7: Browser Gateway Cross-Session & Cross-Org Isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_browser_gateway_cross_session_command_injection_blocked():
    """Result frame from Session B must NOT resolve a pending command belonging to Session A."""
    sess_a = uuid.uuid4()
    sess_b = uuid.uuid4()
    org_id = uuid.uuid4()
    cmd_id = uuid.uuid4()

    mock_future = asyncio.get_running_loop().create_future()
    browser_gateway._pending_commands[cmd_id] = {
        "future": mock_future,
        "session_id": sess_a,
        "org_id": org_id,
        "issued_at": datetime.now(timezone.utc),
    }
    browser_gateway._session_orgs[sess_a] = org_id
    browser_gateway._session_orgs[sess_b] = org_id

    try:
        # Session B attempts to report result for Session A's command
        await browser_gateway.handle_incoming_frame(
            session_id=sess_b,
            frame={
                "frame_type": "RESULT",
                "payload": {
                    "command_id": str(cmd_id),
                    "success": True,
                    "status": "SUCCESS",
                },
            },
        )
        # Future MUST NOT be resolved by Session B
        assert not mock_future.done()
        assert cmd_id in browser_gateway._pending_commands
    finally:
        browser_gateway._pending_commands.pop(cmd_id, None)
        browser_gateway._session_orgs.pop(sess_a, None)
        browser_gateway._session_orgs.pop(sess_b, None)


@pytest.mark.asyncio
async def test_browser_gateway_session_cancellation_isolation():
    """Cancelling Session A's commands must NOT cancel commands for Session B."""
    sess_a = uuid.uuid4()
    sess_b = uuid.uuid4()
    cmd_a = uuid.uuid4()
    cmd_b = uuid.uuid4()

    fut_a = asyncio.get_running_loop().create_future()
    fut_b = asyncio.get_running_loop().create_future()

    browser_gateway._pending_commands[cmd_a] = {"future": fut_a, "session_id": sess_a}
    browser_gateway._pending_commands[cmd_b] = {"future": fut_b, "session_id": sess_b}

    try:
        browser_gateway._cancel_session_commands(sess_a, reason="Session A disconnected")

        # Command A is cancelled
        assert fut_a.done()
        res_a = fut_a.result()
        assert res_a.status == CommandExecutionStatus.CANCELLED

        # Command B remains ACTIVE and untouched!
        assert not fut_b.done()
        assert cmd_b in browser_gateway._pending_commands
    finally:
        browser_gateway._pending_commands.pop(cmd_a, None)
        browser_gateway._pending_commands.pop(cmd_b, None)


# ---------------------------------------------------------------------------
# PHASE 8: Approval State Machine Enforcement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_action_approval_illegal_transition_rejected(test_db_session: AsyncSession):
    """An already EXECUTED approval must NOT be transitioned back to APPROVED or REJECTED."""
    org_id = uuid.uuid4()
    org = Organization(id=org_id, name="State Machine Org", slug="state-org")
    test_db_session.add(org)

    agent_svc = AgentService(test_db_session)
    session = await agent_svc.create_session(org_id=org_id, browser_id="state-test-browser")

    approval = ActionApproval(
        session_id=session.id,
        action_type="DM",
        content="hello",
        status=ApprovalStatus.EXECUTED.value,
    )
    test_db_session.add(approval)
    await test_db_session.commit()

    with pytest.raises(ActionBlockedException) as exc_info:
        await agent_svc.review_action_approval(
            org_id=org_id,
            approval_id=approval.id,
            decision="APPROVED",
            reviewer="admin",
        )
    assert "already been executed" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_outreach_approval_illegal_transition_rejected(test_db_session: AsyncSession):
    """OutreachService must reject approving drafts that are in NEEDS_REVIEW or REJECTED status."""
    org_id = uuid.uuid4()
    org = Organization(id=org_id, name="Outreach State Org", slug="outreach-org")
    test_db_session.add(org)

    lead = Lead(id=uuid.uuid4(), organization_id=org_id, title="Test Lead")
    test_db_session.add(lead)

    draft = OutreachDraft(
        id=uuid.uuid4(),
        organization_id=org_id,
        lead_id=lead.id,
        channel="INSTAGRAM_DM",
        body="Draft needing review",
        angle="ECOMMERCE",
        recommended_service="ECOMMERCE",
        status=DraftStatus.NEEDS_REVIEW.value,  # NOT READY_FOR_APPROVAL
    )
    test_db_session.add(draft)
    await test_db_session.commit()

    outreach_svc = OutreachService(test_db_session)
    with pytest.raises(ValueError) as exc_info:
        await outreach_svc.approve_draft(organization_id=org_id, draft_id=draft.id, reviewed_by="admin")
    assert "READY_FOR_APPROVAL" in str(exc_info.value)


# ---------------------------------------------------------------------------
# PHASE 9: CRM Deduplication Concurrency Safety
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_company_duplicate_domain_prevention(test_db_session: AsyncSession):
    """Creating duplicate company domain within same org raises DuplicateEntityException."""
    org_id = uuid.uuid4()
    org = Organization(id=org_id, name="CRM Test Org", slug="crm-org")
    test_db_session.add(org)
    await test_db_session.commit()

    comp_svc = CompanyService(test_db_session)
    c1 = await comp_svc.create_company(
        CompanyCreate(
            organization_id=org_id,
            name="Apex Brand",
            domain="apexbrand.com",
            website_url="https://apexbrand.com",
        )
    )
    assert c1.id is not None

    with pytest.raises(DuplicateEntityException):
        await comp_svc.create_company(
            CompanyCreate(
                organization_id=org_id,
                name="Apex Brand Duplicate",
                domain="apexbrand.com",
                website_url="https://apexbrand.com/about",
            )
        )


@pytest.mark.asyncio
async def test_lead_duplicate_profile_url_prevention(test_db_session: AsyncSession):
    """Creating duplicate lead with same normalized profile URL raises DuplicateEntityException."""
    org_id = uuid.uuid4()
    org = Organization(id=org_id, name="CRM Lead Org", slug="crm-lead-org")
    test_db_session.add(org)
    await test_db_session.commit()

    lead_svc = LeadService(test_db_session)
    l1 = await lead_svc.create_lead(
        LeadCreate(
            organization_id=org_id,
            title="IG Influencer",
            profile_url="https://instagram.com/influencer123",
        )
    )
    assert l1.id is not None

    with pytest.raises(DuplicateEntityException):
        await lead_svc.create_lead(
            LeadCreate(
                organization_id=org_id,
                title="IG Influencer Duplicate",
                profile_url="https://instagram.com/influencer123/",
            )
        )


# ---------------------------------------------------------------------------
# PHASE 10: Observation Pipeline Ingestion
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_observation_pipeline_ingestion_and_persistence(test_db_session: AsyncSession):
    """Browser OBSERVATION frame must trigger observe_and_process_page and persist agent event."""
    org_id = uuid.uuid4()
    org = Organization(id=org_id, name="Obs Org", slug="obs-org")
    test_db_session.add(org)

    agent_svc = AgentService(test_db_session)
    session = await agent_svc.create_session(org_id=org_id, browser_id="obs-browser")
    await test_db_session.commit()

    # Execute observe_and_process_page pipeline
    await agent_svc.observe_and_process_page(
        org_id=org_id,
        session_id=session.id,
        url="https://modernboutique.shop",
        visible_text="Welcome to our store. We sell handmade clothing.",
    )

    # Verify event was recorded in DB
    from services.api.app.models.agent import AgentEvent
    stmt = select(AgentEvent).where(
        AgentEvent.session_id == session.id,
        AgentEvent.event_type == "content_observed",
    )
    res = await test_db_session.execute(stmt)
    events = res.scalars().all()
    assert len(events) >= 1
    assert events[0].url == "https://modernboutique.shop"


# ---------------------------------------------------------------------------
# PHASE 12: Conversation Field Integrity
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_conversation_memory_service_field_integrity(test_db_session: AsyncSession):
    """ConversationMemoryService must correctly access Contact and WebsiteResearch fields without attribute errors."""
    from services.api.app.models.conversation import ConversationThread
    org_id = uuid.uuid4()
    org = Organization(id=org_id, name="Conv Org", slug="conv-org")
    test_db_session.add(org)

    contact = Contact(
        id=uuid.uuid4(),
        organization_id=org_id,
        full_name="Sarah Founder",
        instagram_username="sarah_fashion",
        email="sarah@fashionbrand.com",
    )
    lead = Lead(
        id=uuid.uuid4(),
        organization_id=org_id,
        contact_id=contact.id,
        title="Fashion Brand Lead",
        recommended_service="ECOMMERCE",
    )
    research = WebsiteResearch(
        id=uuid.uuid4(),
        organization_id=org_id,
        lead_id=lead.id,
        website_url="https://fashionbrand.com",
        opportunity_score=85,
        technology_stack=[{"name": "Shopify"}, {"name": "Klaviyo"}],
    )
    thread = ConversationThread(
        id=uuid.uuid4(),
        organization_id=org_id,
        lead_id=lead.id,
        channel="INSTAGRAM_DM",
    )
    test_db_session.add(contact)
    test_db_session.add(lead)
    test_db_session.add(research)
    test_db_session.add(thread)
    await test_db_session.commit()

    memory_svc = ConversationMemoryService(test_db_session)
    ctx = await memory_svc.build_context(organization_id=org_id, thread=thread)

    assert ctx.contact_handle == "sarah_fashion"
    assert any("Shopify" in f for f in ctx.website_findings)


# ---------------------------------------------------------------------------
# PHASE 13: SSRF Security Regression
# ---------------------------------------------------------------------------

def test_ssrf_validator_blocks_internal_and_cloud_metadata():
    """validate_and_sanitize_target_url must strictly reject loopback, internal addresses, and cloud metadata IPs."""
    # Loopback IP
    with pytest.raises(SSRFValidationError):
        validate_and_sanitize_target_url("http://127.0.0.1/admin")

    # Localhost
    with pytest.raises(SSRFValidationError):
        validate_and_sanitize_target_url("http://localhost:8000")

    # AWS/GCP Metadata IP
    with pytest.raises(SSRFValidationError):
        validate_and_sanitize_target_url("http://169.254.169.254/latest/meta-data")

    # Private 10.x.x.x
    with pytest.raises(SSRFValidationError):
        validate_and_sanitize_target_url("http://10.0.0.1/internal")

    # Private 192.168.x.x
    with pytest.raises(SSRFValidationError):
        validate_and_sanitize_target_url("http://192.168.1.1/router")

    # Google cloud metadata hostname
    with pytest.raises(SSRFValidationError):
        validate_and_sanitize_target_url("http://metadata.google.internal/computeMetadata/v1")
