import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared_types.agent import ApprovalStatus
from packages.shared_types.browser_protocol import (
    BrowserCommandResult,
    CommandExecutionStatus,
    ExtensionSessionState,
    PageState,
    PageType,
)
from packages.shared_types.prospecting import (
    CandidateStatus,
    ProspectingJobStatus,
    ProspectingSourceType,
)
from services.api.app.agents.browser.gateway import BrowserGatewayManager
from services.api.app.agents.prospecting.command_driver import BrowserCommandDriver
from services.api.app.agents.prospecting.extractor import BusinessExtractor
from services.api.app.agents.prospecting.orchestrator import ProspectingOrchestrator
from services.api.app.agents.prospecting.sources.factory import get_source_adapter
from services.api.app.agents.prospecting.sources.instagram import InstagramSource
from services.api.app.agents.prospecting.sources.reddit import RedditSource
from services.api.app.agents.prospecting.sources.threads import ThreadsSource
from services.api.app.agents.prospecting.sources.website import WebsiteSource
from services.api.app.agents.prospecting.sources.web_search import WebSearchSource
from services.api.app.agents.signals.engine import SignalDetectionEngine
from services.api.app.models.agent import ActionApproval, AgentSession
from services.api.app.models.prospecting import ProspectingJob
from services.api.app.schemas.prospecting import ProspectingJobCreate
from services.api.app.services.prospecting_service import ProspectingService

DEFAULT_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


# =====================================================================
# 1. Source Adapters Unit Tests
# =====================================================================

def test_instagram_source_adapter():
    source = InstagramSource()
    assert "explore/tags/barbershop" in source.get_initial_url("#barbershop")
    assert "instagram.com/nike" in source.get_initial_url("@nike")
    assert source.get_initial_url("https://instagram.com/mybrand") == "https://instagram.com/mybrand"

    # Challenge detection
    challenge = source.detect_security_challenge({"visible_text": "Please log in to see photos and videos"})
    assert challenge.is_blocked is True
    assert challenge.challenge_type == "LOGIN_REQUIRED"

    no_challenge = source.detect_security_challenge({"visible_text": "Welcome to Acme Coffee official page"})
    assert no_challenge.is_blocked is False

    # Candidate discovery from profile
    cands = source.discover_candidates({
        "url": "https://www.instagram.com/acmebrand/",
        "page_title": "Acme Brand • Instagram photos and videos",
        "visible_text": "Handcrafted goods in NYC. DM for orders. Visit acmebrand.com",
        "links": ["https://acmebrand.com", "https://instagram.com/p/123/"],
    })
    assert len(cands) >= 1
    assert cands[0].username_or_handle == "@acmebrand"
    assert cands[0].domain == "acmebrand.com"
    assert source.build_dedup_key(cands[0]) == "instagram:acmebrand"


def test_reddit_source_adapter():
    source = RedditSource()
    assert "reddit.com/r/smallbusiness" in source.get_initial_url("r/smallbusiness")
    assert "reddit.com/search/?q=" in source.get_initial_url("need a website")

    # Challenge detection
    challenge = source.detect_security_challenge({"visible_text": "whoa there, to continue, verify you are a human"})
    assert challenge.is_blocked is True
    assert challenge.challenge_type == "CAPTCHA"

    # Disqualification: student homework
    text_hw = "Looking for website advice for school homework assignment"
    assert SignalDetectionEngine.check_false_positive(text_hw) is True
    cands_hw = source.discover_candidates({"visible_text": text_hw, "url": "https://reddit.com/r/webdev"})
    assert len(cands_hw) == 0

    # High intent business request discovery
    valid_text = "Looking for someone to build a new website for our dental clinic in Austin."
    cands_valid = source.discover_candidates({
        "url": "https://www.reddit.com/r/smallbusiness/comments/abc123/need_website/",
        "visible_text": f"Posted by u/austindentist 2 hours ago. {valid_text}",
        "links": [],
    })
    assert len(cands_valid) >= 1
    assert cands_valid[0].platform == "REDDIT"
    assert source.build_dedup_key(cands_valid[0]) in ("reddit_post:abc123", "reddit:austindentist")


def test_threads_and_website_source_adapters():
    th_source = ThreadsSource()
    assert "threads.net/@zuck" in th_source.get_initial_url("@zuck")
    ch = th_source.detect_security_challenge({"visible_text": "Log in with Instagram to view this profile"})
    assert ch.is_blocked is True

    web_source = WebsiteSource()
    cands = web_source.discover_candidates({
        "url": "https://acmesoftware.io/about",
        "page_title": "Acme Software - Enterprise Cloud Solutions",
        "visible_text": "We build fast cloud platforms.",
    })
    assert len(cands) == 1
    assert cands[0].domain == "acmesoftware.io"
    assert web_source.build_dedup_key(cands[0]) == "domain:acmesoftware.io"

    # Visiting /contact on the same site produces the identical deduplication key
    cands_contact = web_source.discover_candidates({
        "url": "https://acmesoftware.io/contact",
        "page_title": "Contact Us - Acme Software",
        "visible_text": "Get in touch with Acme Software.",
    })
    assert web_source.build_dedup_key(cands_contact[0]) == "domain:acmesoftware.io"


# =====================================================================
# 2. Business Extractor Truthfulness Tests
# =====================================================================

def test_business_extractor_truthfulness():
    # Never hallucinate missing company data
    empty_info = BusinessExtractor.extract_business({
        "url": "https://unknownsite.xyz",
        "page_title": "",
        "visible_text": "",
        "links": [],
    })
    assert empty_info.company_name == "Unknownsite" or empty_info.company_name is None
    assert empty_info.public_email is None
    assert empty_info.public_phone is None

    # Realistic business extraction
    real_obs = {
        "url": "https://bakerycafe.com",
        "page_title": "Sweet Crumb Bakery & Cafe | Fresh Pastries in Seattle",
        "visible_text": "Welcome to Sweet Crumb Bakery! Contact us at hello@bakerycafe.com or (206) 555-0199.",
        "links": ["https://bakerycafe.com/menu"],
    }
    extracted = BusinessExtractor.extract_business(real_obs)
    assert extracted.domain == "bakerycafe.com"
    assert extracted.public_email == "hello@bakerycafe.com"
    assert "206" in (extracted.public_phone or "")
    assert extracted.business_category == "Food & Hospitality"
    assert extracted.confidence > 0.5


# =====================================================================
# 3. Signal Engine & Anti-False-Positive Filtering Tests
# =====================================================================

def test_signal_engine_anti_false_positive():
    # 1. Competitor freelancer selling web dev
    freelancer_text = "I am a freelance web developer looking for clients. Hire me for your website!"
    assert SignalDetectionEngine.check_false_positive(freelancer_text) is True
    assert len(SignalDetectionEngine.detect_signals(freelancer_text)) == 0

    # 2. Competitor agency
    agency_text = "We are a web design agency offering SEO and web dev packages for your brand."
    assert SignalDetectionEngine.check_false_positive(agency_text) is True

    # 3. Student / Homework
    student_text = "Need someone to build a website for my school homework assignment."
    assert SignalDetectionEngine.check_false_positive(student_text) is True

    # 4. Genuine Buyer
    buyer_text = "We are launching a new boutique next month and looking for someone to build a new website."
    assert SignalDetectionEngine.check_false_positive(buyer_text) is False
    signals = SignalDetectionEngine.detect_signals(buyer_text)
    assert len(signals) >= 1
    assert SignalDetectionEngine.has_explicit_intent(signals) is True


# =====================================================================
# 4. Command Driver Controlled Scrolling Tests
# =====================================================================

@pytest.mark.asyncio
async def test_command_driver_controlled_scrolling_stops_on_stagnant_content():
    mock_gateway = MagicMock(spec=BrowserGatewayManager)
    mock_gateway.get_page_state.return_value = MagicMock(is_loading=False)
    session_id = uuid.uuid4()
    job_id = uuid.uuid4()

    driver = BrowserCommandDriver(session_id, DEFAULT_ORG_ID, job_id, gateway=mock_gateway)

    # Initial read returns text
    read_result = {"visible_text": "Fixed static footer content", "page_title": "Example"}
    driver.read_page = AsyncMock(return_value=read_result)
    driver.scroll = AsyncMock(return_value=BrowserCommandResult(
        command_id=uuid.uuid4(),
        session_id=session_id,
        success=True,
        status=CommandExecutionStatus.SUCCESS,
        correlation_id="test",
    ))

    # Should detect 3 consecutive identical content reads and stop after 3 scrolls despite max_scrolls=5
    obs_list = await driver.controlled_scroll_and_read(max_scrolls=5, settle_delay=0.01)
    assert len(obs_list) == 1
    assert driver.scroll.call_count == 3


# =====================================================================
# 5. Full Autonomous Prospecting Loop Test (Ready for Approval Stop)
# =====================================================================

@pytest.mark.asyncio
async def test_full_autonomous_prospecting_loop(test_db_session: AsyncSession):
    # 1. Setup active agent session
    agent_session = AgentSession(
        organization_id=DEFAULT_ORG_ID,
        browser_id="test-chrome-browser",
        status=ExtensionSessionState.CONNECTED.value,
    )
    test_db_session.add(agent_session)
    await test_db_session.commit()
    await test_db_session.refresh(agent_session)

    # 2. Setup mock gateway connected to this session
    mock_gateway = MagicMock(spec=BrowserGatewayManager)
    mock_gateway.is_connected.return_value = True

    # Simulate browser returning discovery page with buyer intent
    discovery_page_data = {
        "url": "https://www.instagram.com/explore/tags/austinretail/",
        "page_title": "Austin Retailers • Instagram",
        "visible_text": "Austin Retailers Community. Mentioning @austinbotanicals who is looking for a new website for their store launch!",
        "links": [
            "https://www.instagram.com/austinbotanicals/",
            "https://austinbotanicals.com",
        ],
    }

    # Profile page data
    profile_page_data = {
        "url": "https://www.instagram.com/austinbotanicals/",
        "page_title": "Austin Botanicals • Instagram photos and videos",
        "visible_text": "Organic plants & ceramics. Launching next month and need a new website. austinbotanicals.com hello@austinbotanicals.com",
        "links": ["https://austinbotanicals.com"],
    }

    # Website page data
    website_page_data = {
        "url": "https://austinbotanicals.com",
        "page_title": "Austin Botanicals | Coming Soon",
        "visible_text": "Austin Botanicals official site. Under construction. Launching soon.",
        "links": [],
    }

    async def mock_send_command(cmd, timeout_seconds=15.0, expected_org_id=None):
        if cmd.type.value == "OPEN_PAGE":
            return BrowserCommandResult(
                command_id=cmd.command_id,
                session_id=agent_session.id,
                success=True,
                status=CommandExecutionStatus.SUCCESS,
                correlation_id=cmd.correlation_id,
            )
        elif cmd.type.value == "READ_PAGE":
            target_url = cmd.payload.get("url") or ""
            res_data = discovery_page_data
            if "austinbotanicals.com" in target_url:
                res_data = website_page_data
            return BrowserCommandResult(
                command_id=cmd.command_id,
                session_id=agent_session.id,
                success=True,
                status=CommandExecutionStatus.SUCCESS,
                result=res_data,
                correlation_id=cmd.correlation_id,
            )
        elif cmd.type.value == "SCROLL":
            return BrowserCommandResult(
                command_id=cmd.command_id,
                session_id=agent_session.id,
                success=True,
                status=CommandExecutionStatus.SUCCESS,
                correlation_id=cmd.correlation_id,
            )
        return BrowserCommandResult(
            command_id=cmd.command_id,
            session_id=agent_session.id,
            success=True,
            status=CommandExecutionStatus.SUCCESS,
            correlation_id=cmd.correlation_id,
        )

    mock_gateway.send_command = AsyncMock(side_effect=mock_send_command)
    mock_gateway.get_page_state.return_value = PageState(
        url="https://www.instagram.com/explore/tags/austinretail/",
        page_type=PageType.INSTAGRAM_PROFILE,
        is_loading=False,
    )

    # 3. Create Prospecting Job
    job = ProspectingJob(
        organization_id=DEFAULT_ORG_ID,
        session_id=agent_session.id,
        status=ProspectingJobStatus.CREATED.value,
        source=ProspectingSourceType.INSTAGRAM.value,
        query="austinretail",
        target_service="Business Website",
        max_candidates=1,
        max_pages=5,
        max_scrolls=1,
    )
    test_db_session.add(job)
    await test_db_session.commit()
    await test_db_session.refresh(job)

    # 4. Execute Orchestrator
    orchestrator = ProspectingOrchestrator(test_db_session, gateway=mock_gateway)
    completed_job = await orchestrator.execute_job(job.id, DEFAULT_ORG_ID)

    # 5. Verify Complete Pipeline Output
    assert completed_job.status == ProspectingJobStatus.COMPLETED.value
    assert completed_job.statistics["candidates_found"] >= 1
    assert completed_job.statistics["candidates_qualified"] >= 1
    assert completed_job.statistics["leads_created"] >= 1
    assert completed_job.statistics["outreach_drafted"] >= 1

    # Verify Candidates in Database
    cands = await orchestrator.candidate_repo.list_by_job(job.id, DEFAULT_ORG_ID)
    assert len(cands) >= 1
    first_cand = cands[0]
    assert first_cand.status in (CandidateStatus.CONVERTED_TO_LEAD.value, CandidateStatus.QUALIFIED.value)
    assert first_cand.linked_lead_id is not None

    # Verify Lead Created in CRM
    lead = await orchestrator.lead_service.get_lead(DEFAULT_ORG_ID, first_cand.linked_lead_id)
    assert lead is not None
    assert lead.overall_score > 0
    assert lead.intent_score > 0

    # Verify Outreach Draft is Strictly at READY_FOR_APPROVAL
    drafts = await orchestrator.outreach_service.outreach_repo.list_drafts_by_lead(DEFAULT_ORG_ID, lead.id)
    assert len(drafts) >= 1
    assert drafts[0].status == "READY_FOR_APPROVAL"

    # Verify Safety Boundary: NO message was sent autonomously!
    assert drafts[0].status != "SENT"
    assert drafts[0].status != "EXECUTED"


# =====================================================================
# 6. Security Challenge Blocking Test
# =====================================================================

@pytest.mark.asyncio
async def test_security_challenge_stops_orchestrator(test_db_session: AsyncSession):
    agent_session = AgentSession(
        organization_id=DEFAULT_ORG_ID,
        browser_id="test-chrome-browser",
        status=ExtensionSessionState.CONNECTED.value,
    )
    test_db_session.add(agent_session)
    await test_db_session.commit()

    mock_gateway = MagicMock(spec=BrowserGatewayManager)
    mock_gateway.is_connected.return_value = True

    # Return CAPTCHA barrier page
    async def mock_send_command(cmd, timeout_seconds=15.0, expected_org_id=None):
        if cmd.type.value == "OPEN_PAGE":
            return BrowserCommandResult(
                command_id=cmd.command_id,
                session_id=agent_session.id,
                success=True,
                status=CommandExecutionStatus.SUCCESS,
                correlation_id=cmd.correlation_id,
            )
        elif cmd.type.value == "READ_PAGE":
            return BrowserCommandResult(
                command_id=cmd.command_id,
                session_id=agent_session.id,
                success=True,
                status=CommandExecutionStatus.SUCCESS,
                result={
                    "visible_text": "Please solve this Cloudflare CAPTCHA turnstile challenge to continue",
                    "page_title": "Attention Required! | Cloudflare",
                },
                correlation_id=cmd.correlation_id,
            )
        return BrowserCommandResult(
            command_id=cmd.command_id,
            session_id=agent_session.id,
            success=True,
            status=CommandExecutionStatus.SUCCESS,
            correlation_id=cmd.correlation_id,
        )

    mock_gateway.send_command = AsyncMock(side_effect=mock_send_command)
    mock_gateway.get_page_state.return_value = PageState(url="https://example.com", is_loading=False)

    job = ProspectingJob(
        organization_id=DEFAULT_ORG_ID,
        session_id=agent_session.id,
        status=ProspectingJobStatus.CREATED.value,
        source=ProspectingSourceType.WEBSITE.value,
        query="https://example.com",
    )
    test_db_session.add(job)
    await test_db_session.commit()

    orchestrator = ProspectingOrchestrator(test_db_session, gateway=mock_gateway)
    blocked_job = await orchestrator.execute_job(job.id, DEFAULT_ORG_ID)

    assert blocked_job.status == ProspectingJobStatus.BLOCKED.value
    assert "security challenge" in blocked_job.failure_reason.lower()


# =====================================================================
# 7. Browser Disconnect Resilience Test
# =====================================================================

@pytest.mark.asyncio
async def test_browser_disconnect_resilience(test_db_session: AsyncSession):
    agent_session = AgentSession(
        organization_id=DEFAULT_ORG_ID,
        browser_id="test-chrome-browser",
        status=ExtensionSessionState.CONNECTED.value,
    )
    test_db_session.add(agent_session)
    await test_db_session.commit()

    mock_gateway = MagicMock(spec=BrowserGatewayManager)
    # Simulate disconnected extension
    mock_gateway.is_connected.return_value = False

    job = ProspectingJob(
        organization_id=DEFAULT_ORG_ID,
        session_id=agent_session.id,
        status=ProspectingJobStatus.CREATED.value,
        source=ProspectingSourceType.WEBSITE.value,
        query="https://example.com",
    )
    test_db_session.add(job)
    await test_db_session.commit()

    orchestrator = ProspectingOrchestrator(test_db_session, gateway=mock_gateway)
    paused_job = await orchestrator.execute_job(job.id, DEFAULT_ORG_ID)

    # Job is NOT marked FAILED; it transitions to WAITING_FOR_USER
    assert paused_job.status == ProspectingJobStatus.WAITING_FOR_USER.value
    assert "disconnected" in paused_job.failure_reason.lower()


# =====================================================================
# 8. API Endpoints Integration Test
# =====================================================================

@pytest.mark.asyncio
async def test_prospecting_api_endpoints(client: AsyncClient):
    headers = {
        "X-Organization-Id": str(DEFAULT_ORG_ID),
        "Authorization": "Bearer dev-test-token",
    }

    # 1. Create Job
    create_resp = await client.post(
        "/api/v1/prospecting/jobs",
        json={
            "source": "WEBSITE",
            "query": "https://example.com",
            "max_candidates": 5,
            "max_pages": 10,
        },
        params={"auto_start": False},
        headers=headers,
    )
    assert create_resp.status_code == 201
    job_data = create_resp.json()
    job_id = job_data["id"]
    assert job_data["status"] == "CREATED"

    # 2. Get Job Details
    get_resp = await client.get(f"/api/v1/prospecting/jobs/{job_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == job_id

    # 3. List Jobs
    list_resp = await client.get("/api/v1/prospecting/jobs", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    # 4. Pause and Resume Job
    pause_resp = await client.post(f"/api/v1/prospecting/jobs/{job_id}/pause", headers=headers)
    assert pause_resp.status_code == 200

    resume_resp = await client.post(f"/api/v1/prospecting/jobs/{job_id}/resume", headers=headers)
    assert resume_resp.status_code == 200

    # 5. Cancel Job
    cancel_resp = await client.post(f"/api/v1/prospecting/jobs/{job_id}/cancel", headers=headers)
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELLED"

    # 6. List Candidates & Observations
    cands_resp = await client.get(f"/api/v1/prospecting/jobs/{job_id}/candidates", headers=headers)
    assert cands_resp.status_code == 200
    assert isinstance(cands_resp.json(), list)

    obs_resp = await client.get(f"/api/v1/prospecting/jobs/{job_id}/observations", headers=headers)
    assert obs_resp.status_code == 200
    assert isinstance(obs_resp.json(), list)
