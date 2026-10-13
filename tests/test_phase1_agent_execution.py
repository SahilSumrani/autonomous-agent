import asyncio
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared_types.browser_protocol import (
    BrowserCommand,
    BrowserCommandResult,
    BrowserCommandType,
    CommandExecutionStatus,
    ExtensionSessionState,
)
from packages.shared_types.prospecting import (
    CandidateStatus,
    ProspectingJobEndReason,
    ProspectingJobStatus,
    ProspectingSourceType,
)
from services.api.app.agents.browser.gateway import (
    BrowserGatewayManager,
    SessionNotConnectedException,
)
from services.api.app.agents.prospecting.command_driver import BrowserCommandDriver
from services.api.app.agents.prospecting.orchestrator import ProspectingOrchestrator
from services.api.app.agents.prospecting.worker import prospecting_worker
from services.api.app.models.agent import AgentSession
from services.api.app.models.prospecting import ProspectingJob

DEFAULT_ORG = uuid.UUID("00000000-0000-0000-0000-000000000001")


def create_mock_gateway(session_id: uuid.UUID, page_responses: dict):
    """
    Creates a mock BrowserGatewayManager that returns scripted page contents
    based on the URL navigated to.
    """
    mock_gateway = MagicMock(spec=BrowserGatewayManager)
    mock_gateway.is_connected.return_value = True
    mock_gateway.get_page_state.return_value = MagicMock(is_loading=False)

    current_url_holder = {"url": None}
    commands_history = []

    async def mock_send(cmd: BrowserCommand, **kwargs):
        commands_history.append(cmd)
        if cmd.type == BrowserCommandType.NAVIGATE:
            target_url = cmd.payload.get("target_url")
            current_url_holder["url"] = target_url
            return BrowserCommandResult(
                command_id=cmd.command_id,
                session_id=session_id,
                success=True,
                status=CommandExecutionStatus.SUCCESS,
                result={"target_url": target_url, "status": "complete"},
                correlation_id=cmd.correlation_id,
            )
        elif cmd.type == BrowserCommandType.READ_PAGE:
            curr = current_url_holder["url"]
            resp = page_responses.get(curr, {
                "url": curr,
                "page_title": "Default Page",
                "visible_text": "Sample generic page text with no intent",
                "links": [],
            })
            return BrowserCommandResult(
                command_id=cmd.command_id,
                session_id=session_id,
                success=True,
                status=CommandExecutionStatus.SUCCESS,
                result=resp,
                correlation_id=cmd.correlation_id,
            )
        elif cmd.type in (BrowserCommandType.SCROLL, BrowserCommandType.STOP):
            return BrowserCommandResult(
                command_id=cmd.command_id,
                session_id=session_id,
                success=True,
                status=CommandExecutionStatus.SUCCESS,
                correlation_id=cmd.correlation_id,
            )
        return BrowserCommandResult(
            command_id=cmd.command_id,
            session_id=session_id,
            success=True,
            status=CommandExecutionStatus.SUCCESS,
            correlation_id=cmd.correlation_id,
        )

    mock_gateway.send_command = AsyncMock(side_effect=mock_send)
    mock_gateway.commands_history = commands_history
    return mock_gateway


@pytest.mark.asyncio
async def test_multipage_crawl_and_frontier_dedup(test_db_session: AsyncSession):
    """
    Verifies that the orchestrator visits multiple pages using the source adapter's
    next_urls frontier, deduplicating already-visited URLs, up to max_pages.
    """
    session_id = uuid.uuid4()
    job_id = uuid.uuid4()

    # Agent session in DB
    agent_sess = AgentSession(
        organization_id=DEFAULT_ORG,
        browser_id="test-browser-frontier",
        status=ExtensionSessionState.CONNECTED.value,
    )
    test_db_session.add(agent_sess)
    await test_db_session.commit()

    page1_url = "https://example.com/blog"
    page2_url = "https://example.com/blog/about"
    page3_url = "https://example.com/blog/contact"

    page_responses = {
        page1_url: {
            "url": page1_url,
            "page_title": "Tech Blog",
            "visible_text": "Welcome to our blog. Check out our services.",
            "links": [
                page2_url,
                page3_url,
                page1_url,  # duplicate
            ],
        },
        page2_url: {
            "url": page2_url,
            "page_title": "About Us",
            "visible_text": "About our team and history.",
            "links": [page1_url, page3_url],
        },
        page3_url: {
            "url": page3_url,
            "page_title": "Contact Us",
            "visible_text": "Get in touch for consultations.",
            "links": [],
        },
    }

    mock_gateway = create_mock_gateway(session_id, page_responses)

    job = ProspectingJob(
        id=job_id,
        organization_id=DEFAULT_ORG,
        source=ProspectingSourceType.WEBSITE.value,
        query=page1_url,
        session_id=session_id,
        status=ProspectingJobStatus.QUEUED.value,
        max_candidates=5,
        max_pages=3,
        max_scrolls=1,
        statistics={},
    )
    test_db_session.add(job)
    await test_db_session.commit()

    orchestrator = ProspectingOrchestrator(session=test_db_session, gateway=mock_gateway)
    with patch("services.api.app.agents.prospecting.orchestrator.EventDispatcher.dispatch", new=AsyncMock()):
        result_job = await orchestrator.execute_job(job_id=job_id, organization_id=DEFAULT_ORG, override_session_id=session_id)

    # All 3 pages visited
    assert result_job.statistics["pages_visited"] == 3
    # Checkpoint contains visited_urls
    meta = result_job.metadata_json or {}
    assert set(meta.get("visited_urls", [])) == {page1_url, page2_url, page3_url}
    # Ended with NO_QUALIFIED_FOUND because none had commercial buying intent
    assert result_job.end_reason == ProspectingJobEndReason.NO_QUALIFIED_FOUND.value


@pytest.mark.asyncio
async def test_disqualified_candidate_does_not_abort_job(test_db_session: AsyncSession):
    """
    Verifies that a disqualified candidate (e.g. competitor or false positive) on page 1
    does NOT terminate the job; orchestrator continues to subsequent pages.
    """
    session_id = uuid.uuid4()
    job_id = uuid.uuid4()

    page1_url = "https://www.reddit.com/r/smallbusiness/"
    page2_url = "https://www.reddit.com/r/smallbusiness/?after=page2"

    page_responses = {
        page1_url: {
            "url": page1_url,
            "page_title": "Small Business Community - Page 1",
            "visible_text": "Community page 1",
            "content_units": [
                {
                    "author": "agencyspammer",
                    "title": "I build websites for startups DM me",
                    "body": "I am a freelancer offering cheap dev services. DM me.",
                }
            ],
            "links": [page2_url],
        },
        page2_url: {
            "url": page2_url,
            "page_title": "Small Business Community - Page 2",
            "visible_text": "Looking for someone to build a new website for our dental clinic in Austin. Posted by u/austindentist 2 hours ago.",
            "content_units": [
                {
                    "author": "austindentist",
                    "title": "Need a new website for our clinic",
                    "url": "https://www.reddit.com/r/smallbusiness/comments/post2/need_website/",
                    "body": "Looking for someone to build a new website for our dental clinic in Austin. Please contact us.",
                }
            ],
            "links": [],
        },
    }

    mock_gateway = create_mock_gateway(session_id, page_responses)

    job = ProspectingJob(
        id=job_id,
        organization_id=DEFAULT_ORG,
        source=ProspectingSourceType.REDDIT.value,
        query="r/smallbusiness",
        session_id=session_id,
        status=ProspectingJobStatus.QUEUED.value,
        max_candidates=1,
        max_pages=2,
        max_scrolls=1,
        statistics={},
    )
    test_db_session.add(job)
    await test_db_session.commit()

    orchestrator = ProspectingOrchestrator(session=test_db_session, gateway=mock_gateway)
    with patch("services.api.app.agents.prospecting.orchestrator.EventDispatcher.dispatch", new=AsyncMock()):
        result_job = await orchestrator.execute_job(job_id=job_id, organization_id=DEFAULT_ORG, override_session_id=session_id)

    # Job proceeded to page 2 despite disqualification on page 1
    assert result_job.statistics["pages_visited"] == 2
    assert result_job.statistics.get("candidates_disqualified", 0) >= 1
    assert result_job.statistics.get("candidates_qualified", 0) == 1
    assert result_job.end_reason == ProspectingJobEndReason.OBJECTIVE_MET.value


@pytest.mark.asyncio
async def test_blocked_keeps_glow_no_stop_command_sent(test_db_session: AsyncSession):
    """
    Verifies that when a CAPTCHA or security challenge is detected, the job status
    becomes BLOCKED (end_reason BLOCKED) and driver.stop() is NOT sent, keeping the
    extension's red BLOCKED glow active for the user.
    """
    session_id = uuid.uuid4()
    job_id = uuid.uuid4()

    challenge_url = "https://www.reddit.com/r/smallbusiness/"
    page_responses = {
        challenge_url: {
            "url": challenge_url,
            "page_title": "Verification Required",
            "visible_text": "whoa there, to continue, verify you are a human. Captcha challenge.",
            "links": [],
        }
    }

    mock_gateway = create_mock_gateway(session_id, page_responses)

    job = ProspectingJob(
        id=job_id,
        organization_id=DEFAULT_ORG,
        source=ProspectingSourceType.REDDIT.value,
        query="r/smallbusiness",
        session_id=session_id,
        status=ProspectingJobStatus.QUEUED.value,
        max_candidates=5,
        max_pages=5,
        max_scrolls=1,
        statistics={},
    )
    test_db_session.add(job)
    await test_db_session.commit()

    orchestrator = ProspectingOrchestrator(session=test_db_session, gateway=mock_gateway)
    with patch("services.api.app.agents.prospecting.orchestrator.EventDispatcher.dispatch", new=AsyncMock()):
        result_job = await orchestrator.execute_job(job_id=job_id, organization_id=DEFAULT_ORG, override_session_id=session_id)

    assert result_job.status == ProspectingJobStatus.BLOCKED.value
    assert result_job.end_reason == ProspectingJobEndReason.BLOCKED.value

    # Verify NO STOP command was dispatched over WebSocket
    stop_commands = [c for c in mock_gateway.commands_history if c.type == BrowserCommandType.STOP]
    assert len(stop_commands) == 0


@pytest.mark.asyncio
async def test_browser_disconnect_ends_in_waiting_for_user(test_db_session: AsyncSession):
    """
    Verifies that a browser disconnect mid-job sets status WAITING_FOR_USER
    with end_reason BROWSER_DISCONNECTED (never COMPLETED).
    """
    session_id = uuid.uuid4()
    job_id = uuid.uuid4()

    mock_gateway = MagicMock(spec=BrowserGatewayManager)
    # Simulate browser disconnected
    mock_gateway.is_connected.return_value = False

    job = ProspectingJob(
        id=job_id,
        organization_id=DEFAULT_ORG,
        source=ProspectingSourceType.WEBSITE.value,
        query="https://example.com",
        session_id=session_id,
        status=ProspectingJobStatus.QUEUED.value,
        max_candidates=5,
        max_pages=5,
        max_scrolls=1,
        statistics={},
    )
    test_db_session.add(job)
    await test_db_session.commit()

    orchestrator = ProspectingOrchestrator(session=test_db_session, gateway=mock_gateway)
    with patch("services.api.app.agents.prospecting.orchestrator.EventDispatcher.dispatch", new=AsyncMock()):
        result_job = await orchestrator.execute_job(job_id=job_id, organization_id=DEFAULT_ORG, override_session_id=session_id)

    assert result_job.status == ProspectingJobStatus.WAITING_FOR_USER.value
    assert result_job.end_reason == ProspectingJobEndReason.BROWSER_DISCONNECTED.value


@pytest.mark.asyncio
async def test_pause_and_resume_continues_from_checkpoint(test_db_session: AsyncSession):
    """
    Verifies that pausing saves checkpoint (visited_urls + frontier) in metadata_json,
    and resuming reloads the frontier instead of starting over from the initial page.
    """
    session_id = uuid.uuid4()
    job_id = uuid.uuid4()

    page1_url = "https://example.com/p1"
    page2_url = "https://example.com/p2"

    page_responses = {
        page1_url: {
            "url": page1_url,
            "page_title": "Page 1",
            "visible_text": "Page 1 text content without intent.",
            "links": [page2_url],
        },
        page2_url: {
            "url": page2_url,
            "page_title": "Page 2",
            "visible_text": "Page 2 text content without intent.",
            "links": [],
        },
    }

    mock_gateway = create_mock_gateway(session_id, page_responses)

    # Simulate existing checkpoint after page 1 was visited
    job = ProspectingJob(
        id=job_id,
        organization_id=DEFAULT_ORG,
        source=ProspectingSourceType.WEBSITE.value,
        query=page1_url,
        session_id=session_id,
        status=ProspectingJobStatus.PAUSED.value,
        max_candidates=5,
        max_pages=5,
        max_scrolls=1,
        statistics={"pages_visited": 1},
        metadata_json={
            "visited_urls": [page1_url],
            "frontier": [page2_url],
            "pages_visited": 1,
        },
    )
    test_db_session.add(job)
    await test_db_session.commit()

    orchestrator = ProspectingOrchestrator(session=test_db_session, gateway=mock_gateway)
    with patch("services.api.app.agents.prospecting.orchestrator.EventDispatcher.dispatch", new=AsyncMock()):
        result_job = await orchestrator.execute_job(job_id=job_id, organization_id=DEFAULT_ORG, override_session_id=session_id)

    # Page 1 was not re-visited; only page 2 was visited
    assert result_job.statistics["pages_visited"] == 2
    meta = result_job.metadata_json or {}
    assert set(meta.get("visited_urls", [])) == {page1_url, page2_url}
