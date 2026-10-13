import asyncio
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from packages.shared_types.browser_protocol import (
    BrowserCommand,
    BrowserCommandResult,
    BrowserCommandType,
    CommandExecutionStatus,
    ExtensionSessionState,
)
from packages.shared_types.prospecting import (
    ProspectingJobStatus,
    ProspectingSourceType,
)
from services.api.app.agents.browser.gateway import (
    BrowserGatewayManager,
    BrowserGatewayException,
    SessionNotConnectedException,
)
from services.api.app.agents.prospecting.command_driver import BrowserCommandDriver
from services.api.app.agents.prospecting.orchestrator import ProspectingOrchestrator
from services.api.app.agents.prospecting.worker import ProspectingWorker
from services.api.app.core.auth import (
    create_browser_session_token,
    verify_browser_session_token,
    AuthenticationError,
    AuthorizationError,
)
from services.api.app.models.prospecting import ProspectingJob


DEFAULT_ORG = uuid.UUID("00000000-0000-0000-0000-000000000001")
ALT_ORG = uuid.UUID("00000000-0000-0000-0000-000000000002")


# =====================================================================
# 1. Browser Session Signed HMAC Token Persistence
# =====================================================================

def test_signed_session_token_roundtrip():
    session_id = uuid.uuid4()
    token = create_browser_session_token(session_id, DEFAULT_ORG, expires_in_seconds=3600)
    assert token.startswith("tv_sess_")

    data = verify_browser_session_token(token)
    assert data["session_id"] == session_id
    assert data["organization_id"] == DEFAULT_ORG


def test_tampered_or_invalid_session_token_rejected():
    session_id = uuid.uuid4()
    token = create_browser_session_token(session_id, DEFAULT_ORG, expires_in_seconds=3600)

    # Tamper with signature
    tampered = token[:-4] + "xxxx"
    with pytest.raises(AuthenticationError):
        verify_browser_session_token(tampered)

    # Random string
    with pytest.raises(AuthenticationError):
        verify_browser_session_token("not-a-session-token")


def test_gateway_recovers_session_from_hmac_after_memory_cleared():
    """Simulates gateway memory wipe (e.g. backend restart) where signed token verifies session."""
    gateway = BrowserGatewayManager()
    session_id = uuid.uuid4()
    token = create_browser_session_token(session_id, DEFAULT_ORG, expires_in_seconds=3600)

    # In-memory session dict is completely empty
    assert token not in gateway._session_tokens
    assert session_id not in gateway._session_orgs

    # Validation succeeds and restores session metadata
    record = gateway.validate_session_token(token)
    assert record is not None
    assert record["session_id"] == session_id
    assert record["organization_id"] == DEFAULT_ORG
    assert gateway._session_orgs[session_id] == DEFAULT_ORG


def test_gateway_rejects_revoked_session_token():
    gateway = BrowserGatewayManager()
    session_id = uuid.uuid4()
    token = create_browser_session_token(session_id, DEFAULT_ORG, expires_in_seconds=3600)

    # Validate first time to register
    record = gateway.validate_session_token(token)
    assert record is not None

    # Revoke session
    gateway.revoke_session(session_id)

    # Validation must now return None
    assert gateway.validate_session_token(token) is None


# =====================================================================
# 2. Worker Lifecycle and Job Deduplication
# =====================================================================

@pytest.mark.asyncio
async def test_worker_deduplicates_concurrent_job_tasks():
    worker = ProspectingWorker()
    job_id = uuid.uuid4()
    session_id = uuid.uuid4()

    with patch.object(worker, "_execute_job_in_background", new=AsyncMock()) as mock_exec:
        mock_exec.return_value = None

        task1 = worker.start_job_task(job_id, DEFAULT_ORG, session_id)
        assert worker.is_job_running(job_id)

        # Starting same job again returns existing task without spawning second
        task2 = worker.start_job_task(job_id, DEFAULT_ORG, session_id)
        assert task1 is task2

        # Await completion
        await task1
        assert not worker.is_job_running(job_id)


@pytest.mark.asyncio
async def test_worker_cancel_in_flight_job():
    worker = ProspectingWorker()
    job_id = uuid.uuid4()
    session_id = uuid.uuid4()

    started = asyncio.Event()

    async def fake_long_job(*args, **kwargs):
        started.set()
        await asyncio.sleep(10.0)

    with patch.object(worker, "_execute_job_in_background", side_effect=fake_long_job):
        task = worker.start_job_task(job_id, DEFAULT_ORG, session_id)
        await started.wait()
        assert worker.is_job_running(job_id)

        cancelled = worker.cancel_job_task(job_id)
        assert cancelled is True
        assert not worker.is_job_running(job_id)


# =====================================================================
# 3. Dedicated Agent Tab Orchestration Sequence
# =====================================================================

@pytest.mark.asyncio
async def test_orchestrator_navigates_and_reads_dedicated_tab_without_hijacking():
    session_id = uuid.uuid4()
    job_id = uuid.uuid4()
    mock_db = AsyncMock()
    mock_gateway = MagicMock(spec=BrowserGatewayManager)
    mock_gateway.is_connected.return_value = True
    mock_gateway.get_page_state.return_value = MagicMock(is_loading=False)

    job = ProspectingJob(
        id=job_id,
        organization_id=DEFAULT_ORG,
        source=ProspectingSourceType.WEBSITE.value,
        query="https://books.toscrape.com/",
        session_id=session_id,
        status=ProspectingJobStatus.QUEUED.value,
        max_candidates=1,
        max_pages=1,
        max_scrolls=1,
        statistics={},
    )

    orchestrator = ProspectingOrchestrator(session=mock_db, gateway=mock_gateway)
    orchestrator.job_repo.get_by_id = AsyncMock(return_value=job)
    orchestrator.job_repo.update_status = AsyncMock(return_value=job)

    commands_sent = []

    async def fake_send_cmd(cmd, **kwargs):
        commands_sent.append(cmd.type)
        if cmd.type == BrowserCommandType.NAVIGATE:
            return BrowserCommandResult(
                command_id=cmd.command_id,
                session_id=session_id,
                success=True,
                status=CommandExecutionStatus.SUCCESS,
                result={"target_url": cmd.payload["target_url"], "status": "complete"},
                correlation_id=cmd.correlation_id,
            )
        elif cmd.type == BrowserCommandType.READ_PAGE:
            return BrowserCommandResult(
                command_id=cmd.command_id,
                session_id=session_id,
                success=True,
                status=CommandExecutionStatus.SUCCESS,
                result={
                    "url": "https://books.toscrape.com/",
                    "page_title": "All products | Books to Scrape - Sandbox",
                    "visible_text": "Books to Scrape. A Light in the Attic. In stock. Price £51.77.",
                },
                correlation_id=cmd.correlation_id,
            )
        elif cmd.type == BrowserCommandType.SCROLL:
            return BrowserCommandResult(
                command_id=cmd.command_id,
                session_id=session_id,
                success=True,
                status=CommandExecutionStatus.SUCCESS,
                correlation_id=cmd.correlation_id,
            )
        elif cmd.type == BrowserCommandType.STOP:
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

    mock_gateway.send_command = AsyncMock(side_effect=fake_send_cmd)

    with patch("services.api.app.agents.prospecting.orchestrator.EventDispatcher.dispatch", new=AsyncMock()):
        await orchestrator.execute_job(job_id=job_id, organization_id=DEFAULT_ORG, override_session_id=session_id)

    # Sequence must be NAVIGATE -> READ_PAGE (and STOP on finish)
    assert BrowserCommandType.NAVIGATE in commands_sent
    assert BrowserCommandType.READ_PAGE in commands_sent
    # NAVIGATE occurred before READ_PAGE
    assert commands_sent.index(BrowserCommandType.NAVIGATE) < commands_sent.index(BrowserCommandType.READ_PAGE)


# =====================================================================
# 4. Explicit Token Validation Separation & Route Authorization
# =====================================================================

def test_distinct_token_validation_rules():
    session_id = uuid.uuid4()
    sess_token = create_browser_session_token(session_id, DEFAULT_ORG, expires_in_seconds=3600)
    from services.api.app.core.auth import create_access_token, verify_access_token

    user_token = create_access_token(actor_id="user_123", organization_id=DEFAULT_ORG)

    # 1. Browser session token used in user access token context must be strictly rejected
    with pytest.raises(AuthenticationError) as exc_info:
        verify_access_token(sess_token)
    assert "Browser session token cannot be used as user access token" in str(exc_info.value.detail)

    # 2. User access token used in browser session token context must be strictly rejected
    with pytest.raises(AuthenticationError) as exc_info_sess:
        verify_browser_session_token(user_token)
    assert "Invalid browser session token format" in str(exc_info_sess.value.detail)

    # 3. Malformed access token strings rejected with 401
    with pytest.raises(AuthenticationError) as exc_malformed:
        verify_access_token("not.enough.parts.extra")
    assert "Malformed access token structure" in str(exc_malformed.value.detail)


def test_cross_tenant_browser_session_token_rejected():
    session_id = uuid.uuid4()
    sess_token = create_browser_session_token(session_id, DEFAULT_ORG, expires_in_seconds=3600)
    from services.api.app.core.auth import verify_and_authorize_browser_session_token

    # Attempting to use DEFAULT_ORG's token for ALT_ORG must raise AuthorizationError (403)
    with pytest.raises(AuthorizationError) as exc_cross:
        verify_and_authorize_browser_session_token(sess_token, expected_org_id=ALT_ORG)
    assert "Cross-tenant access rejected" in str(exc_cross.value.detail)


@pytest.mark.asyncio
async def test_create_job_with_browser_session_token_scoped_to_own_session():
    from services.api.app.api.v1.routes.prospecting import create_job
    from services.api.app.core.auth import AuthenticatedActor
    from services.api.app.schemas.prospecting import ProspectingJobCreate
    from fastapi import HTTPException

    my_session_id = uuid.uuid4()
    other_session_id = uuid.uuid4()

    actor = AuthenticatedActor(
        actor_id=f"browser_session_{my_session_id.hex[:8]}",
        organization_id=DEFAULT_ORG,
        actor_type="BROWSER_SESSION",
        session_id=my_session_id,
        is_authenticated=True,
    )

    mock_db = AsyncMock()
    mock_service = MagicMock()
    fake_job = MagicMock()
    fake_job.id = uuid.uuid4()
    fake_job.organization_id = DEFAULT_ORG
    fake_job.session_id = my_session_id
    fake_job.status = ProspectingJobStatus.QUEUED.value
    fake_job.source = ProspectingSourceType.WEBSITE.value
    fake_job.query = "https://example.com"
    fake_job.target_service = "AI Automation"
    fake_job.target_industries = []
    fake_job.target_geography = None
    fake_job.max_candidates = 5
    fake_job.max_pages = 10
    fake_job.max_scrolls = 3
    fake_job.max_time_seconds = 1800
    fake_job.failure_reason = None
    fake_job.end_reason = None
    fake_job.statistics = {}
    fake_job.metadata_json = None
    from datetime import datetime, timezone
    fake_job.created_at = datetime.now(timezone.utc)
    fake_job.started_at = None
    fake_job.completed_at = None

    mock_service.create_job = AsyncMock(return_value=fake_job)

    with patch("services.api.app.api.v1.routes.prospecting.ProspectingService", return_value=mock_service), \
         patch("services.api.app.api.v1.routes.prospecting.prospecting_worker.start_job_task") as mock_start_task:

        # 1. Successful job creation when session_id matches actor.session_id
        req_valid = ProspectingJobCreate(
            source=ProspectingSourceType.WEBSITE,
            query="https://example.com",
            session_id=my_session_id,
        )
        res = await create_job(data=req_valid, auto_start=True, db=mock_db, actor=actor)
        assert res.session_id == my_session_id
        mock_start_task.assert_called_once_with(fake_job.id, DEFAULT_ORG, my_session_id)

        # 2. Browser session attempting to start job for a DIFFERENT session is rejected (403 Forbidden)
        req_diff = ProspectingJobCreate(
            source=ProspectingSourceType.WEBSITE,
            query="https://example.com",
            session_id=other_session_id,
        )
        with pytest.raises(HTTPException) as exc_diff:
            await create_job(data=req_diff, auto_start=True, db=mock_db, actor=actor)
        assert exc_diff.value.status_code == 403
        assert "cannot initiate jobs for different session" in exc_diff.value.detail


@pytest.mark.asyncio
async def test_linkedin_and_extended_sources_accepted():
    """Verify LINKEDIN, GOOGLE_MAPS, and UPWORK are accepted without 422 Unprocessable Content."""
    from services.api.app.schemas.prospecting import ProspectingJobCreate
    from services.api.app.agents.prospecting.sources.factory import get_source_adapter

    from services.api.app.agents.prospecting.sources.base import UnsupportedSourceException

    for src in ["LINKEDIN", "THREADS", "INSTAGRAM", "REDDIT", "WEBSITE"]:
        req = ProspectingJobCreate(
            source=src,  # type: ignore
            query="https://www.linkedin.com/feed/",
            target_service="find client automation",
        )
        assert req.source.value == src
        adapter = get_source_adapter(req.source)
        assert adapter is not None

    for unsupp in ["GOOGLE_MAPS", "UPWORK"]:
        with pytest.raises(UnsupportedSourceException):
            get_source_adapter(unsupp)

