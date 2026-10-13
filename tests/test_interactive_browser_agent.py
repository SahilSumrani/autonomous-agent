import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock

from packages.shared_types.browser_protocol import (
    BrowserCommand,
    BrowserCommandResult,
    BrowserCommandType,
    CommandExecutionStatus,
)
from packages.shared_types.prospecting import (
    CandidateStatus,
    ProspectingJobStatus,
    ProspectingSourceType,
)
from services.api.app.agents.prospecting.command_driver import BrowserCommandDriver
from services.api.app.agents.signals.country_detector import (
    CountryDetectionEngine,
    CountryEvidence,
)


def test_country_detection_india():
    # 1. Indian domain
    res1 = CountryDetectionEngine.evaluate(domain="techservices.co.in")
    assert res1.country == "INDIA"
    assert res1.confidence >= 0.95

    # 2. Indian phone prefix
    res2 = CountryDetectionEngine.evaluate(text="Contact us at +91 9876543210 for web design")
    assert res2.country == "INDIA"
    assert res2.confidence >= 0.95

    # 3. City + currency
    res3 = CountryDetectionEngine.evaluate(text="Looking for a web development agency in Bengaluru. Budget is ₹50,000.")
    assert res3.country == "INDIA"
    assert res3.city_or_state == "Bengaluru"
    assert "₹" in res3.evidence or "Bengaluru" in res3.evidence


def test_country_detection_usa():
    # 1. US domain
    res1 = CountryDetectionEngine.evaluate(domain="state.ca.gov")
    assert res1.country == "USA"
    assert res1.confidence >= 0.95

    # 2. US State / City + currency
    res2 = CountryDetectionEngine.evaluate(text="Our dental clinic in Austin, Texas needs a complete website redesign. Budget $5,000.")
    assert res2.country == "USA"
    assert res2.confidence >= 0.80

    # 3. Explicit mention
    res3 = CountryDetectionEngine.evaluate(text="We are a small business based in the United States looking for an app developer.")
    assert res3.country == "USA"
    assert res3.confidence >= 0.80


def test_country_detection_no_fabrication():
    # Ambiguous or generic text without country signal must return None (zero hallucination)
    res = CountryDetectionEngine.evaluate(text="Need a developer to build an MVP for our startup.")
    assert res.country is None
    assert res.confidence == 0.0
    assert res.evidence is None


@pytest.mark.asyncio
async def test_command_driver_typing_and_key_press():
    mock_gateway = MagicMock()
    mock_gateway.is_connected.return_value = True

    async def mock_send(cmd: BrowserCommand, **kwargs):
        return BrowserCommandResult(
            command_id=cmd.command_id,
            session_id=cmd.session_id,
            success=True,
            status=CommandExecutionStatus.SUCCESS,
            result={"typed_text": cmd.payload.get("text")},
            duration_ms=10.0,
        )

    mock_gateway.send_command = AsyncMock(side_effect=mock_send)

    session_id = uuid.uuid4()
    org_id = uuid.uuid4()
    job_id = uuid.uuid4()
    driver = BrowserCommandDriver(session_id=session_id, org_id=org_id, job_id=job_id, gateway=mock_gateway)

    # Test type_text
    type_res = await driver.type_text(text="hire web developer", selector="input[name='q']")
    assert type_res.success is True
    assert mock_gateway.send_command.call_count == 1
    sent_cmd = mock_gateway.send_command.call_args[0][0]
    assert sent_cmd.type == BrowserCommandType.TYPE_TEXT
    assert sent_cmd.payload["text"] == "hire web developer"

    # Test press_key
    press_res = await driver.press_key(key="Enter")
    assert press_res.success is True
    sent_key_cmd = mock_gateway.send_command.call_args[0][0]
    assert sent_key_cmd.type == BrowserCommandType.PRESS_KEY
    assert sent_key_cmd.payload["key"] == "Enter"


@pytest.mark.asyncio
async def test_command_driver_interactive_search():
    mock_gateway = MagicMock()
    mock_gateway.is_connected.return_value = True

    async def mock_send(cmd: BrowserCommand, **kwargs):
        if cmd.type == BrowserCommandType.FIND_SEARCH_INPUT:
            return BrowserCommandResult(
                command_id=cmd.command_id,
                session_id=cmd.session_id,
                success=True,
                status=CommandExecutionStatus.SUCCESS,
                result={"found": True, "selector": "input[name='q']"},
                duration_ms=5.0,
            )
        return BrowserCommandResult(
            command_id=cmd.command_id,
            session_id=cmd.session_id,
            success=True,
            status=CommandExecutionStatus.SUCCESS,
            result={"success": True},
            duration_ms=5.0,
        )

    mock_gateway.send_command = AsyncMock(side_effect=mock_send)
    mock_gateway.get_page_state.return_value = MagicMock(is_loading=False)

    session_id = uuid.uuid4()
    driver = BrowserCommandDriver(session_id=session_id, org_id=uuid.uuid4(), job_id=uuid.uuid4(), gateway=mock_gateway)

    search_res = await driver.interactive_search("hire flutter developer")
    assert search_res["success"] is True
    assert search_res["selector"] == "input[name='q']"
    assert search_res["query"] == "hire flutter developer"


def test_threads_source_extracts_real_client_posts_from_user_screen():
    from services.api.app.agents.prospecting.sources.threads import ThreadsSource

    th_source = ThreadsSource()
    obs = {
        "url": "https://www.threads.com/",
        "visible_text": """
apostlegiftobazee 1h
Recommend anyone who can develop an app for business purposes at a Considerable rate. Send me a Whatsapp message on 07058618259
3 7
josephine638.6 > Interior Design 40m
Lf graphic designer, dm me please!!!
1 6
miller_oleg_ 4h
Looking for a partner to find and manage clients.
London, England
44 50 1 1
dreammedia_in 48m
Looking for AI video creators/editors
Not so high budget but eventually invest if we see improvement and compatibility!
8 13 1
deeper.ferdi 3h
Looking for video editor. Short form Ugc style. Pm or comment with rates.
        """,
    }

    candidates = th_source.discover_candidates(obs)
    assert len(candidates) >= 4

    handles = [c.username_or_handle for c in candidates]
    assert "@apostlegiftobazee" in handles
    assert "@josephine638.6" in handles
    assert "@dreammedia_in" in handles
    assert "@deeper.ferdi" in handles

    # Verify app development intent on apostlegiftobazee
    app_cand = next(c for c in candidates if c.username_or_handle == "@apostlegiftobazee")
    assert "07058618259" in app_cand.evidence
    assert app_cand.platform == "THREADS"
    assert "threads.com" in app_cand.canonical_url


def test_threads_source_search_and_recency_urls():
    from services.api.app.agents.prospecting.sources.threads import ThreadsSource

    th_source = ThreadsSource()
    # Direct search with recency
    url = th_source.get_initial_url("looking for a developer")
    assert "threads.com/search" in url
    assert "q=looking%20for%20a%20developer" in url
    assert "filter=recent" in url

    # Default entry URLs include feed and recent search
    entry_urls = th_source.get_entry_urls(None)
    assert "https://www.threads.com/" in entry_urls
    assert any("filter=recent" in u for u in entry_urls)
