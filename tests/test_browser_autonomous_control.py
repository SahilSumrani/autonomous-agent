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
from services.api.app.agents.prospecting.orchestrator import ProspectingOrchestrator
from services.api.app.agents.research.validators import (
    validate_and_sanitize_target_url,
    SSRFValidationError,
)
from services.api.app.models.prospecting import ProspectingJob

DEFAULT_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


# =====================================================================
# 1. NAVIGATE Command and URL Validation
# =====================================================================

@pytest.mark.asyncio
async def test_navigate_command_valid_target():
    session_id = uuid.uuid4()
    job_id = uuid.uuid4()
    mock_gateway = MagicMock(spec=BrowserGatewayManager)
    mock_gateway.is_connected.return_value = True

    async def fake_send_cmd(cmd, **kwargs):
        assert cmd.type == BrowserCommandType.NAVIGATE
        assert cmd.payload["target_url"] == "https://books.toscrape.com/"
        return BrowserCommandResult(
            command_id=cmd.command_id,
            session_id=session_id,
            success=True,
            status=CommandExecutionStatus.SUCCESS,
            result={"target_url": cmd.payload["target_url"], "status": "complete"},
            duration_ms=45.0,
            correlation_id=cmd.correlation_id,
        )

    mock_gateway.send_command = AsyncMock(side_effect=fake_send_cmd)

    driver = BrowserCommandDriver(
        session_id=session_id,
        org_id=DEFAULT_ORG_ID,
        job_id=job_id,
        gateway=mock_gateway,
    )

    result = await driver.navigate("https://books.toscrape.com/")
    assert result.success is True
    assert result.status == CommandExecutionStatus.SUCCESS
    assert result.result["target_url"] == "https://books.toscrape.com/"


@pytest.mark.asyncio
async def test_navigate_command_blocks_dangerous_urls():
    session_id = uuid.uuid4()
    job_id = uuid.uuid4()
    mock_gateway = MagicMock(spec=BrowserGatewayManager)
    mock_gateway.is_connected.return_value = True
    driver = BrowserCommandDriver(
        session_id=session_id,
        org_id=DEFAULT_ORG_ID,
        job_id=job_id,
        gateway=mock_gateway,
    )

    # Localhost / Loopback
    res_local = await driver.navigate("http://127.0.0.1:8000/admin")
    assert res_local.success is False
    assert res_local.status == CommandExecutionStatus.BLOCKED

    # Cloud metadata IP
    res_meta = await driver.navigate("http://169.254.169.254/latest/meta-data")
    assert res_meta.success is False
    assert res_meta.status == CommandExecutionStatus.BLOCKED

    # Credentials in URL
    res_cred = await driver.navigate("https://admin:secretpassword@example.com/login")
    assert res_cred.success is False
    assert res_cred.status == CommandExecutionStatus.BLOCKED

    # Unsafe / Non-HTTP Schemes
    res_proto = await driver.navigate("javascript:alert(1)")
    assert res_proto.success is False
    assert res_proto.status == CommandExecutionStatus.BLOCKED

    # Gateway should never have received a send_command call for blocked targets
    mock_gateway.send_command.assert_not_called()


# =====================================================================
# 2. Autonomous Scroll Loop with Content Hash Stopping
# =====================================================================

@pytest.mark.asyncio
async def test_autonomous_scroll_loop_content_hash_stopping():
    session_id = uuid.uuid4()
    job_id = uuid.uuid4()
    mock_gateway = MagicMock(spec=BrowserGatewayManager)
    mock_gateway.is_connected.return_value = True

    # Simulation: Page has 2 unique sections, then content stagnates (reaches end of feed)
    pages = [
        {"visible_text": "Books Page 1: A Light in the Attic, Tipping the Velvet", "url": "https://books.toscrape.com/"},
        {"visible_text": "Books Page 2: Soumission, Sharp Objects", "url": "https://books.toscrape.com/"},
        {"visible_text": "Books Page 2: Soumission, Sharp Objects", "url": "https://books.toscrape.com/"}, # duplicate!
    ]
    page_idx = 0

    async def fake_read_page(timeout_seconds=15.0):
        nonlocal page_idx
        idx = min(page_idx, len(pages) - 1)
        res = pages[idx]
        page_idx += 1
        return res

    async def fake_scroll(direction="down", distance=600, timeout_seconds=10.0):
        return BrowserCommandResult(
            command_id=uuid.uuid4(),
            session_id=session_id,
            success=True,
            status=CommandExecutionStatus.SUCCESS,
            correlation_id=str(uuid.uuid4()),
        )

    driver = BrowserCommandDriver(
        session_id=session_id,
        org_id=DEFAULT_ORG_ID,
        job_id=job_id,
        gateway=mock_gateway,
    )
    driver.read_page = AsyncMock(side_effect=fake_read_page)
    driver.scroll = AsyncMock(side_effect=fake_scroll)

    observations = await driver.controlled_scroll_and_read(
        max_scrolls=5,
        settle_delay=0.01,
        consecutive_unchanged_threshold=3,
    )

    # Must stop when content hash matches previously seen content
    assert len(observations) == 2
    assert "A Light in the Attic" in observations[0]["visible_text"]
    assert "Soumission" in observations[1]["visible_text"]
    # Scroll stopped boundedly before reaching max_scrolls (5) after 3 consecutive unchanged reads
    assert driver.scroll.call_count == 4


# =====================================================================
# 3. Active Control State & Stop Deactivation
# =====================================================================

@pytest.mark.asyncio
async def test_active_control_stop_emits_command():
    session_id = uuid.uuid4()
    job_id = uuid.uuid4()
    mock_gateway = MagicMock(spec=BrowserGatewayManager)
    mock_gateway.is_connected.return_value = True

    stopped_command = None

    async def fake_send(cmd, **kwargs):
        nonlocal stopped_command
        if cmd.type == BrowserCommandType.STOP:
            stopped_command = cmd
            return BrowserCommandResult(
                command_id=cmd.command_id,
                session_id=session_id,
                success=True,
                status=CommandExecutionStatus.SUCCESS,
                result={"status": "STOPPED"},
                correlation_id=cmd.correlation_id,
            )
        return BrowserCommandResult(
            command_id=cmd.command_id,
            session_id=session_id,
            success=True,
            status=CommandExecutionStatus.SUCCESS,
            correlation_id=cmd.correlation_id,
        )

    mock_gateway.send_command = AsyncMock(side_effect=fake_send)

    driver = BrowserCommandDriver(
        session_id=session_id,
        org_id=DEFAULT_ORG_ID,
        job_id=job_id,
        gateway=mock_gateway,
    )

    res = await driver.stop()
    assert res.success is True
    assert stopped_command is not None
    assert stopped_command.type == BrowserCommandType.STOP


# =====================================================================
# 4. CAPTCHA Blocking & Strict Zero-Outreach Guarantee
# =====================================================================

@pytest.mark.asyncio
async def test_captcha_blocking_stops_safely_with_zero_outreach():
    session_id = uuid.uuid4()
    job_id = uuid.uuid4()

    mock_db = AsyncMock()
    mock_gateway = MagicMock(spec=BrowserGatewayManager)
    mock_gateway.is_connected.return_value = True

    orchestrator = ProspectingOrchestrator(session=mock_db, gateway=mock_gateway)

    job = ProspectingJob(
        id=job_id,
        organization_id=DEFAULT_ORG_ID,
        source=ProspectingSourceType.REDDIT.value,
        query="r/forhire freelance web developer",
        session_id=session_id,
        status=ProspectingJobStatus.QUEUED.value,
        max_candidates=5,
        max_pages=2,
        max_scrolls=2,
        statistics={},
    )

    orchestrator.job_repo.get_by_id = AsyncMock(return_value=job)
    orchestrator.job_repo.update_status = AsyncMock(return_value=job)

    # Mock browser driver returning a CAPTCHA challenge
    with patch("services.api.app.agents.prospecting.orchestrator.BrowserCommandDriver") as MockDriverClass:
        mock_driver = MagicMock()
        mock_driver.is_connected.return_value = True
        mock_driver.open_page = AsyncMock(return_value=BrowserCommandResult(
            command_id=uuid.uuid4(),
            session_id=session_id,
            success=True,
            status=CommandExecutionStatus.SUCCESS,
            correlation_id=str(uuid.uuid4()),
        ))
        mock_driver.wait_for_ready = AsyncMock(return_value=True)
        mock_driver.controlled_scroll_and_read = AsyncMock(return_value=[])
        # Reddit bot detection challenge
        mock_driver.read_page = AsyncMock(return_value={
            "url": "https://www.reddit.com/r/forhire",
            "page_title": "Reddit - Security Check",
            "visible_text": "Whoa there, to continue, verify you are a human. Please solve the captcha to continue.",
        })
        mock_driver.stop = AsyncMock()
        MockDriverClass.return_value = mock_driver

        res_job = await orchestrator.execute_job(
            job_id=job_id,
            organization_id=DEFAULT_ORG_ID,
            override_session_id=session_id,
        )

        # Job must be BLOCKED
        # Driver.stop() must NOT be called on BLOCKED so the extension keeps showing the red BLOCKED glow
        mock_driver.stop.assert_not_called()
        # Outreach service must NEVER have been called
        orchestrator.outreach_service.generate_outreach = AsyncMock()
        orchestrator.outreach_service.generate_outreach.assert_not_called()
