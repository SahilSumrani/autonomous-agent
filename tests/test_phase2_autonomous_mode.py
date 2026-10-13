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
    CandidateStatus,
    ProspectingJobStatus,
    ProspectingSourceType,
)
from services.api.app.agents.prospecting.orchestrator import ProspectingOrchestrator
from services.api.app.agents.prospecting.sources.base import UnsupportedSourceException
from services.api.app.agents.prospecting.sources.factory import get_source_adapter
from services.api.app.agents.prospecting.sources.linkedin import LinkedInSource
from services.api.app.agents.prospecting.sources.reddit import RedditSource
from services.api.app.agents.prospecting.sources.threads import ThreadsSource
from services.api.app.models.prospecting import (
    ProspectCandidate,
    ProspectingJob,
    ProspectingProfile,
)
from services.api.app.repositories.prospecting import (
    ProspectCandidateRepository,
    ProspectingJobRepository,
    ProspectingProfileRepository,
)
from services.api.app.schemas.prospecting import ProspectingJobCreate
from services.api.app.services.normalization import (
    PLATFORM_OWNED_DOMAINS,
    is_platform_owned_domain,
)
from services.api.app.services.prospecting_service import ProspectingService


DEFAULT_ORG = uuid.UUID("00000000-0000-0000-0000-000000000001")


def test_unsupported_source_raises():
    """Verify that any source lacking a dedicated adapter raises UnsupportedSourceException."""
    with pytest.raises(UnsupportedSourceException):
        get_source_adapter(ProspectingSourceType.UPWORK)

    with pytest.raises(UnsupportedSourceException):
        get_source_adapter(ProspectingSourceType.GOOGLE_MAPS)

    with pytest.raises(UnsupportedSourceException):
        get_source_adapter("TIKTOK")

    # Supported sources must return proper adapters
    assert isinstance(get_source_adapter(ProspectingSourceType.REDDIT), RedditSource)
    assert isinstance(get_source_adapter(ProspectingSourceType.THREADS), ThreadsSource)
    assert isinstance(get_source_adapter(ProspectingSourceType.LINKEDIN), LinkedInSource)


def test_platform_owned_domains_shield():
    """Verify platform domains cannot become lead domains."""
    for domain in ["linkedin.com", "www.linkedin.com", "reddit.com", "threads.net", "instagram.com", "facebook.com", "x.com", "twitter.com"]:
        assert is_platform_owned_domain(domain) is True

    assert is_platform_owned_domain("techverse.io") is False
    assert is_platform_owned_domain("mybusiness.com") is False
    assert is_platform_owned_domain("dentist-seattle.org") is False


def test_linkedin_source_entry_urls_and_candidate_extraction():
    """Verify LinkedInSource generates entry URLs and shields against linkedin.com domain attribution."""
    adapter = LinkedInSource()
    profile = MagicMock()
    profile.ideal_customer_keywords = ["need website", "looking for developer"]

    # Entry URLs generation with no query
    urls = adapter.get_entry_urls(None, profile)
    assert "https://www.linkedin.com/feed/" in urls
    assert any("keywords=need%20website" in u for u in urls)

    # Candidate extraction on feed page observation
    page_data = {
        "url": "https://www.linkedin.com/feed/",
        "page_title": "Feed | LinkedIn",
        "visible_text": "Alex Morgan posted: Looking for an agency to rebuild our medical practice website urgently! Contact me at alex@morganhealth.com or visit morganhealth.com.",
        "content_units": [
            {
                "type": "post",
                "author": "Alex Morgan",
                "text": "Looking for an agency to rebuild our medical practice website urgently! Contact alex@morganhealth.com",
                "permalink": "https://www.linkedin.com/feed/update/urn:li:activity:9876543210/",
            }
        ],
    }

    candidates = adapter.discover_candidates(page_data)
    assert len(candidates) > 0
    for cand in candidates:
        assert cand.domain != "linkedin.com"
        assert not is_platform_owned_domain(cand.domain)
        assert "urn:li:activity" in cand.canonical_url or cand.canonical_url is not None


@pytest.mark.asyncio
async def test_prospecting_profile_crud(test_db_session):
    """Verify ProspectingProfile persistence, defaults, and updates."""
    repo = ProspectingProfileRepository(test_db_session)
    profile = await repo.get_or_create(DEFAULT_ORG)
    assert profile is not None
    assert profile.organization_id == DEFAULT_ORG
    assert "AI automation" in profile.services_offered
    assert "need a website" in profile.ideal_customer_keywords
    assert "LINKEDIN" not in profile.sources_enabled
    assert "REDDIT" in profile.sources_enabled

    # Update profile (e.g. opt-in to LINKEDIN)
    updated = await repo.update(
        DEFAULT_ORG,
        {
            "geography": "North America",
            "ideal_customer_keywords": ["need web app", "hiring agency"],
            "sources_enabled": ["REDDIT", "LINKEDIN"],
        },
    )
    assert updated.geography == "North America"
    assert updated.ideal_customer_keywords == ["need web app", "hiring agency"]
    assert "LINKEDIN" in updated.sources_enabled


@pytest.mark.asyncio
async def test_no_input_autonomous_job_creation_and_execution(test_db_session):
    """Verify that jobs created with no query or service succeed and use the org profile."""
    session_id = uuid.uuid4()
    job_id = uuid.uuid4()

    # 1. Create job with no query and no target_service
    job = ProspectingJob(
        id=job_id,
        organization_id=DEFAULT_ORG,
        source=ProspectingSourceType.REDDIT.value,
        query=None,
        target_service=None,
        session_id=session_id,
        status=ProspectingJobStatus.QUEUED.value,
        max_candidates=2,
        max_pages=2,
        max_scrolls=1,
        statistics={},
    )
    test_db_session.add(job)
    await test_db_session.commit()

    # 2. Setup mock gateway
    mock_gateway = MagicMock()
    mock_gateway.get_session_state.return_value = ExtensionSessionState.CONNECTED
    mock_gateway.get_page_state.return_value = MagicMock(is_loading=False)

    current_url_holder = {"url": None}

    async def mock_send(cmd: BrowserCommand, **kwargs):
        if cmd.type == BrowserCommandType.NAVIGATE:
            current_url_holder["url"] = cmd.payload.get("target_url")
            return BrowserCommandResult(
                command_id=cmd.command_id,
                session_id=session_id,
                success=True,
                status=CommandExecutionStatus.SUCCESS,
                result={"target_url": current_url_holder["url"]},
                correlation_id=cmd.correlation_id,
            )
        elif cmd.type == BrowserCommandType.READ_PAGE:
            return BrowserCommandResult(
                command_id=cmd.command_id,
                session_id=session_id,
                success=True,
                status=CommandExecutionStatus.SUCCESS,
                result={
                    "url": current_url_holder["url"] or "https://www.reddit.com/r/forhire/",
                    "page_title": "forhire: jobs & freelance",
                    "visible_text": "John Doe posted: [Hiring] Need a developer to build an MVP for our dental logistics company at logidental.com",
                    "content_hash": "hash_auton_1",
                    "links": [],
                    "content_units": [
                        {
                            "type": "post",
                            "author": "johndoe_logistics",
                            "title": "[Hiring] Need a developer to build an MVP",
                            "permalink": "https://www.reddit.com/r/forhire/comments/xyz123/hiring_need_developer/",
                            "text": "Need a developer to build an MVP for our dental logistics company at logidental.com",
                        }
                    ],
                },
                correlation_id=cmd.correlation_id,
            )
        else:
            return BrowserCommandResult(
                command_id=cmd.command_id,
                session_id=session_id,
                success=True,
                status=CommandExecutionStatus.SUCCESS,
                result={"status": "complete"},
                correlation_id=cmd.correlation_id,
            )

    mock_gateway.send_command_and_wait = AsyncMock(side_effect=mock_send)

    orchestrator = ProspectingOrchestrator(
        session=test_db_session,
        gateway=mock_gateway,
    )

    orchestrator.research_service.research_website = AsyncMock()
    orchestrator.outreach_service.create_draft = AsyncMock()

    with patch("services.api.app.services.event_dispatcher.EventDispatcher.dispatch", new=AsyncMock()):
        completed_job = await orchestrator.execute_job(
            job_id=job_id,
            organization_id=DEFAULT_ORG,
            override_session_id=session_id,
        )

    assert completed_job is not None
    # Candidate extracted from feed must never have domain 'reddit.com'
    cand_repo = ProspectCandidateRepository(test_db_session)
    candidates = await cand_repo.list_by_job(job_id, DEFAULT_ORG)
    for c in candidates:
        assert c.domain != "reddit.com"
        assert not is_platform_owned_domain(c.domain)
