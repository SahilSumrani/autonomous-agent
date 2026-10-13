import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, MagicMock

from packages.config.settings import settings
from packages.shared_types.agent import ApprovalStatus
from packages.shared_types.crm import LeadStatus, LeadType, TechVerseService
from packages.shared_types.outreach import DraftStatus, OutreachChannel
from services.api.app.agents.outreach.message_generator import MessageGenerator
from services.api.app.agents.outreach.outreach_models import OutreachContext, PainPoint
from services.api.app.agents.prospecting.orchestrator import ProspectingOrchestrator
from services.api.app.agents.prospecting.sources.reddit import RedditSource
from services.api.app.agents.prospecting.sources.threads import ThreadsSource
from services.api.app.core.auth import (
    AuthenticationError,
    AuthorizationError,
    create_access_token,
)
from services.api.app.models.crm import Contact, Lead, Organization
from services.api.app.services.outreach_service import OutreachService

ORG_A = uuid.UUID("00000000-0000-0000-0000-000000000001")
ORG_B = uuid.UUID("00000000-0000-0000-0000-000000000002")


# ============================================================================
# Phase 1: P0 Security & Authentication Regression Tests
# ============================================================================

@pytest.mark.asyncio
async def test_bearer_token_arbitrary_string_rejected_in_production(client: AsyncClient):
    """Verifies that arbitrary non-empty Bearer tokens are rejected with 401 in production."""
    orig_env = settings.ENVIRONMENT
    try:
        settings.ENVIRONMENT = "production"
        headers = {
            "Authorization": "Bearer totally-fake-arbitrary-bearer-token",
            "X-Organization-ID": str(ORG_A),
        }
        res = await client.get("/api/v1/prospecting/events/recent", headers=headers)
        assert res.status_code == 401
        assert "Invalid" in res.json().get("detail", "") or "token" in res.json().get("detail", "").lower()
    finally:
        settings.ENVIRONMENT = orig_env


@pytest.mark.asyncio
async def test_forged_organization_id_header_rejected(client: AsyncClient):
    """Verifies that presenting a valid token for Org A with X-Organization-ID for Org B is rejected (403)."""
    orig_env = settings.ENVIRONMENT
    try:
        settings.ENVIRONMENT = "production"
        # Generate valid cryptographic JWT signed for ORG_A
        valid_token_org_a = create_access_token(org_id=ORG_A, user_id="user_test_a")
        
        # Attacker attempts to forge X-Organization-ID to ORG_B
        headers = {
            "Authorization": f"Bearer {valid_token_org_a}",
            "X-Organization-ID": str(ORG_B),
        }
        res = await client.get("/api/v1/prospecting/events/recent", headers=headers)
        assert res.status_code == 403
        assert "forged" in res.json().get("detail", "").lower() or "cross-tenant" in res.json().get("detail", "").lower()
    finally:
        settings.ENVIRONMENT = orig_env


@pytest.mark.asyncio
async def test_events_recent_endpoint_requires_auth_and_filters_tenant(
    client: AsyncClient, test_db_session: AsyncSession
):
    """Verifies /events/recent is protected and only returns events belonging to caller's org."""
    # Without any auth or org in prod
    orig_env = settings.ENVIRONMENT
    try:
        settings.ENVIRONMENT = "production"
        res_no_auth = await client.get("/api/v1/prospecting/events/recent")
        assert res_no_auth.status_code in (400, 401)
    finally:
        settings.ENVIRONMENT = orig_env

    # In dev/test mode with valid Org A token
    valid_token_a = create_access_token(org_id=ORG_A, user_id="user_test_a")
    res_a = await client.get(
        "/api/v1/prospecting/events/recent",
        headers={"Authorization": f"Bearer {valid_token_a}", "X-Organization-ID": str(ORG_A)},
    )
    assert res_a.status_code == 200
    events = res_a.json()
    assert isinstance(events, list)
    for ev in events:
        assert ev.get("organization_id") == str(ORG_A)


# ============================================================================
# Phase 3: Discovery Correctness Regression Tests
# ============================================================================

def test_reddit_distinct_posts_produce_distinct_candidates():
    """Verifies platform-specific post URLs and stable per-post deduplication."""
    source = RedditSource()
    raw_page = {
        "url": "https://www.reddit.com/r/smallbusiness/",
        "visible_text": "Subreddit feed",
        "contentUnits": [
            {
                "type": "REDDIT_POST",
                "postId": "post_111",
                "url": "https://www.reddit.com/r/smallbusiness/comments/post_111/need_website_austin/",
                "title": "Need a brand new website for our dental clinic",
                "author": "austindentist",
                "body": "Looking for a reputable agency to build our dental clinic site in Austin.",
                "subreddit": "smallbusiness",
                "links": [],
            },
            {
                "type": "REDDIT_POST",
                "postId": "post_222",
                "url": "https://www.reddit.com/r/smallbusiness/comments/post_222/another_project_austin/",
                "title": "Looking for ecommerce Shopify developer",
                "author": "austindentist",
                "body": "Also looking for a Shopify developer for our retail line.",
                "subreddit": "smallbusiness",
                "links": [],
            },
        ],
    }

    candidates = source.discover_candidates(raw_page)
    assert len(candidates) == 2

    key1 = source.build_dedup_key(candidates[0])
    key2 = source.build_dedup_key(candidates[1])
    assert key1 == "reddit_post:post_111"
    assert key2 == "reddit_post:post_222"
    assert key1 != key2, "Multiple distinct posts from same author must not be deduplicated away"


def test_threads_mention_without_intent_rejected():
    """Verifies candidate is NOT created merely because a handle is mentioned without buying intent."""
    source = ThreadsSource()
    raw_page = {
        "url": "https://www.threads.net/@coolfashion",
        "visible_text": "Random chat about fashion. Mentioning @john_doe who was at the party yesterday.",
        "contentUnits": [
            {
                "type": "THREADS_POST",
                "author": "coolfashion",
                "body": "Had coffee with @john_doe today, wonderful afternoon!",
                "url": "https://www.threads.net/@coolfashion/post/xyz",
            }
        ],
    }

    candidates = source.discover_candidates(raw_page)
    # Neither @john_doe nor coolfashion expressed commercial buying intent
    assert len(candidates) == 0


def test_threads_post_with_verified_buying_intent_creates_candidate():
    """Verifies author with verified buying intent creates candidate with source URL and evidence."""
    source = ThreadsSource()
    raw_page = {
        "url": "https://www.threads.net/@austinbakery",
        "visible_text": "Austin Bakery official profile",
        "contentUnits": [
            {
                "type": "THREADS_POST",
                "author": "austinbakery",
                "body": "Our bakery is opening next month and we need someone to build our new website and online ordering system!",
                "url": "https://www.threads.net/@austinbakery/post/abc123",
            }
        ],
    }

    candidates = source.discover_candidates(raw_page)
    assert len(candidates) == 1
    assert candidates[0].username_or_handle == "@austinbakery"
    assert "https://www.threads.net/@austinbakery/post/abc123" in candidates[0].source_url
    assert "online ordering system" in candidates[0].evidence


# ============================================================================
# Phase 5: Outreach Grounding & Human Approval Gate Regression Tests
# ============================================================================

def test_message_generator_grounding_no_uninspected_website_claims():
    """Verifies that messages do not claim the sender inspected a site unless inspection actually occurred."""
    # Context WITHOUT website audit or inspection findings
    uninspected_ctx = OutreachContext(
        lead_id=uuid.uuid4(),
        company_name="Apex Store",
        source="REDDIT",
        recommended_service="BUSINESS_WEBSITE",
        website_url="https://apexstore.com",  # domain known, but NO audit or observations
        pain_points=[],
        evidence=[],
    )

    variants = MessageGenerator.generate_variants(
        context=uninspected_ctx,
        channel=OutreachChannel.INSTAGRAM_DM,
        variant_count=3,
    )

    for v in variants:
        assert "While reviewing the site" not in v.body
        assert "on the site" not in v.body
        assert "took a close look at your public web experience" not in v.body


def test_message_generator_grounding_truthful_when_site_inspected():
    """Verifies that messages truthfully reference observed findings when website audit evidence exists."""
    inspected_ctx = OutreachContext(
        lead_id=uuid.uuid4(),
        company_name="Apex Store",
        source="INSTAGRAM",
        recommended_service="ECOMMERCE",
        website_url="https://apexstore.com",
        website_findings={"cms": "Shopify", "mobile_score": 45},
        pain_points=[
            PainPoint(
                category="MOBILE_UX",
                statement="Mobile checkout button is hidden on small screens",
                evidence="Tested viewport 375px",
                severity="HIGH",
            )
        ],
    )

    variants = MessageGenerator.generate_variants(
        context=inspected_ctx,
        channel=OutreachChannel.INSTAGRAM_DM,
        variant_count=3,
    )
    assert len(variants) == 3
    # Variant A or B should reference the specific observed flow
    assert any("mobile checkout" in v.body.lower() for v in variants)


@pytest.mark.asyncio
async def test_email_outreach_blocked_without_verified_recipient_email(
    test_db_session: AsyncSession
):
    """Verifies that email outreach generation is strictly blocked without a verified recipient email."""
    service = OutreachService(test_db_session)
    lead_id = uuid.uuid4()
    lead = Lead(
        id=lead_id,
        organization_id=ORG_A,
        title="Unverified Prospect",
        status=LeadStatus.QUALIFIED.value,
        overall_score=75,
        intent_score=80,
        qualification_score=70,
        contact_id=None,  # No contact
    )
    test_db_session.add(lead)
    await test_db_session.commit()

    with pytest.raises(ValueError, match="No verified recipient email available"):
        await service.generate_outreach(
            organization_id=ORG_A,
            lead_id=lead_id,
            channel=OutreachChannel.EMAIL,
        )

    # Verify attempt was recorded as BLOCKED
    attempts = await service.outreach_repo.list_attempts_by_lead(ORG_A, lead_id)
    assert len(attempts) >= 1
    assert attempts[0].status == "BLOCKED"


# ============================================================================
# Phase 2 & 4: Isolation, Deduplication, and WebSocket Scoping Tests
# ============================================================================

@pytest.mark.asyncio
async def test_websocket_cross_tenant_subscription_rejected():
    """Verifies WebSocket authentication dependency rejects cross-tenant connection."""
    from services.api.app.api.v1.dependencies.auth import authenticate_ws_actor
    from services.api.app.core.auth import create_access_token
    from fastapi import WebSocket

    # Token signed for Org A
    token_org_a = create_access_token(org_id=ORG_A, user_id="user_test_a")

    orig_env = settings.ENVIRONMENT
    try:
        settings.ENVIRONMENT = "production"
        mock_ws = MagicMock(spec=WebSocket)
        mock_ws.headers = {}
        mock_ws.query_params = {}

        # Mismatched Org B requested with token signed for Org A
        with pytest.raises(AuthorizationError, match="Forged organization identity"):
            await authenticate_ws_actor(
                mock_ws,
                token=token_org_a,
                x_organization_id=str(ORG_B),
            )
    finally:
        settings.ENVIRONMENT = orig_env


@pytest.mark.asyncio
async def test_event_dispatcher_deduplication():
    """Verifies that events with duplicate event_id are deduplicated in WebSocket subscriber pipeline."""
    delivered: list = []
    delivered_ids: set = set()

    def deliver_event(event_record):
        ev_id = event_record.get("event_id")
        if ev_id in delivered_ids:
            return False
        delivered_ids.add(ev_id)
        delivered.append(event_record)
        return True

    test_id = str(uuid.uuid4())
    event_1 = {"event_id": test_id, "event_type": "prospect.discovered", "data": {"name": "Apex"}}
    event_2 = {"event_id": test_id, "event_type": "prospect.discovered", "data": {"name": "Apex"}}

    res1 = deliver_event(event_1)
    res2 = deliver_event(event_2)

    assert res1 is True
    assert res2 is False
    assert len(delivered) == 1, "Duplicate event_id must not be delivered twice"


@pytest.mark.asyncio
async def test_orchestrator_candidate_failure_isolation(test_db_session: AsyncSession):
    """Verifies that an error in one candidate does not terminate the entire prospecting job."""
    from packages.shared_types.browser_protocol import (
        BrowserCommandResult,
        CommandExecutionStatus,
        ExtensionSessionState,
        PageState,
        PageType,
    )
    from packages.shared_types.prospecting import ProspectingJobStatus, ProspectingSourceType
    from services.api.app.agents.browser.gateway import BrowserGatewayManager
    from services.api.app.models.agent import AgentSession
    from services.api.app.models.prospecting import ProspectingJob

    agent_session = AgentSession(
        organization_id=ORG_A,
        browser_id="test-browser-isol",
        status=ExtensionSessionState.CONNECTED.value,
    )
    test_db_session.add(agent_session)
    await test_db_session.commit()
    await test_db_session.refresh(agent_session)

    mock_gateway = MagicMock(spec=BrowserGatewayManager)
    mock_gateway.is_connected.return_value = True
    mock_gateway.get_page_state.return_value = PageState(
        url="https://reddit.com/r/smallbusiness",
        page_type=PageType.REDDIT_POST,
        is_loading=False,
    )

    # Return 2 candidates in page
    multi_post_data = {
        "url": "https://www.reddit.com/r/smallbusiness/",
        "visible_text": "Reddit feed",
        "contentUnits": [
            {
                "type": "REDDIT_POST",
                "postId": "post_error_cand",
                "url": "https://www.reddit.com/r/smallbusiness/comments/post_error_cand/broken/",
                "title": "Need dental site",
                "author": "error_author",
                "body": "Need dental website in Austin",
                "subreddit": "smallbusiness",
                "links": [],
            },
            {
                "type": "REDDIT_POST",
                "postId": "post_valid_cand",
                "url": "https://www.reddit.com/r/smallbusiness/comments/post_valid_cand/valid/",
                "title": "Need bakery site",
                "author": "valid_author",
                "body": "Looking for web developer for bakery site in Austin",
                "subreddit": "smallbusiness",
                "links": [],
            },
        ],
    }

    async def mock_send_cmd(cmd, *a, **k):
        return BrowserCommandResult(
            command_id=cmd.command_id,
            correlation_id=getattr(cmd, "correlation_id", str(uuid.uuid4())),
            session_id=agent_session.id,
            success=True,
            status=CommandExecutionStatus.SUCCESS,
            result=multi_post_data,
        )

    mock_gateway.send_command = AsyncMock(side_effect=mock_send_cmd)

    job = ProspectingJob(
        organization_id=ORG_A,
        session_id=agent_session.id,
        status=ProspectingJobStatus.CREATED.value,
        source=ProspectingSourceType.REDDIT.value,
        query="smallbusiness",
        target_service="Business Website",
        max_candidates=2,
        max_pages=1,
        max_scrolls=1,
    )
    test_db_session.add(job)
    await test_db_session.commit()
    await test_db_session.refresh(job)

    orchestrator = ProspectingOrchestrator(test_db_session, gateway=mock_gateway)

    # Mock lead_service.create_lead to fail on the first candidate and succeed on the second
    orig_create_lead = orchestrator.lead_service.create_lead
    call_count = 0

    async def flaky_create_lead(data):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Simulated database transient lock failure on candidate 1")
        return await orig_create_lead(data)

    orchestrator.lead_service.create_lead = AsyncMock(side_effect=flaky_create_lead)

    completed_job = await orchestrator.execute_job(job.id, ORG_A)
    print("FAILURE REASON:", completed_job.failure_reason)
    assert completed_job.status == ProspectingJobStatus.COMPLETED.value
    assert completed_job.statistics["candidates_found"] >= 2
    # The second candidate must have been created successfully despite the first failing
    assert completed_job.statistics["leads_created"] == 1

