import pytest
import re
import uuid
from unittest.mock import AsyncMock, MagicMock
from packages.shared_types.prospecting import CandidateStatus
from packages.shared_types.crm import SignalType
from services.api.app.services.normalization import (
    clean_social_post_text,
    is_disallowed_business_domain,
    is_platform_owned_domain,
    normalize_domain,
)
from services.api.app.agents.signals.engine import SignalDetectionEngine
from services.api.app.agents.prospecting.sources.website import WebsiteSource
from services.api.app.agents.prospecting.sources.linkedin import LinkedInSource
from services.api.app.agents.prospecting.sources.threads import ThreadsSource
from services.api.app.agents.prospecting.extractor import BusinessExtractor


# ==============================================================================
# DEFECT 1: example.com and placeholder websites rejected / not qualified
# ==============================================================================
def test_defect_1_example_com_and_placeholders_rejected():
    """Verify example.com, test.com and placeholders are disallowed and not discovered as business leads."""
    assert is_disallowed_business_domain("example.com") is True
    assert is_disallowed_business_domain("www.example.com") is True
    assert is_disallowed_business_domain("test.com") is True
    assert is_disallowed_business_domain("sample.com") is True
    assert is_disallowed_business_domain("placeholder.com") is True
    assert is_disallowed_business_domain("localhost") is True

    # Real businesses should NOT be disallowed
    assert is_disallowed_business_domain("acme-roofing.com") is False
    assert is_disallowed_business_domain("techverse.io") is False

    # WebsiteSource initial url fallback should NOT default to example.com
    src = WebsiteSource()
    assert src.get_initial_url("") == ""
    assert src.get_initial_url(None) == ""

    # WebsiteSource discover_candidates must reject example.com and pages with no intent signals
    page_data = {
        "url": "https://example.com/",
        "page_title": "Example Domain",
        "visible_text": "This domain is for use in illustrative examples in documents.",
    }
    candidates = src.discover_candidates(page_data)
    assert len(candidates) == 0, "Placeholder domain example.com must not be emitted as a candidate"


# ==============================================================================
# DEFECT 2: LinkedIn leads must not display generic 'Discovered Prospect'
# ==============================================================================
def test_defect_2_linkedin_unattributable_members_and_feeds_rejected():
    """Verify anonymous members or generic feed observations are rejected rather than becoming 'Discovered Prospect'."""
    src = LinkedInSource()

    # Generic feed update with 'LinkedIn Member'
    page_data_anonymous = {
        "url": "https://www.linkedin.com/feed/",
        "posts": [
            {
                "author": "LinkedIn Member",
                "text": "We need a website developer immediately for our startup.",
                "url": "https://www.linkedin.com/feed/update/urn:li:activity:12345",
            }
        ]
    }
    candidates = src.discover_candidates(page_data_anonymous)
    assert len(candidates) == 0, "Anonymous LinkedIn Member must not be emitted as candidate"

    # Attributable real author with explicit intent
    page_data_real = {
        "url": "https://www.linkedin.com/feed/",
        "posts": [
            {
                "author": "Sarah Connor",
                "text": "We need a web designer to rebuild our company website this month.",
                "url": "https://www.linkedin.com/posts/sarahconnor_update_12345",
            }
        ]
    }
    candidates = src.discover_candidates(page_data_real)
    assert len(candidates) == 1
    assert candidates[0].company_name == "Sarah Connor"
    assert candidates[0].username_or_handle == "in/sarah_connor"
    assert "Discovered Prospect" not in candidates[0].company_name


# ==============================================================================
# DEFECT 3: gmail.com and email providers are never treated as business websites
# ==============================================================================
def test_defect_3_email_domains_never_treated_as_business_websites():
    """Verify gmail.com, yahoo.com, outlook.com, etc. are rejected as company websites."""
    assert is_disallowed_business_domain("gmail.com") is True
    assert is_disallowed_business_domain("googlemail.com") is True
    assert is_disallowed_business_domain("yahoo.com") is True
    assert is_disallowed_business_domain("outlook.com") is True
    assert is_disallowed_business_domain("hotmail.com") is True
    assert is_disallowed_business_domain("icloud.com") is True

    # Test BusinessExtractor when visible text contains an email address
    obs = {
        "visible_text": "Contact our team at sales@gmail.com or visit our office.",
        "url": "https://www.linkedin.com/in/someuser",
        "title": "Some User Profile",
        "links": ["https://gmail.com", "mailto:sales@gmail.com"],
    }
    biz = BusinessExtractor.extract_business(obs, profile_url="https://www.linkedin.com/in/someuser")
    assert biz.domain != "gmail.com", "gmail.com must never be set as company domain"


# ==============================================================================
# DEFECT 4: Low-intent and review-required records are not converted to CRM leads
# ==============================================================================
def test_defect_4_developer_self_promo_and_job_seekers_disqualified():
    """Verify developers advertising services or job seekers are disqualified, not converted."""
    # Developer pitching their own services
    dev_pitch = "I design and build high converting websites for startups. DM me for web dev services! Here is my portfolio."
    assert SignalDetectionEngine.check_false_positive(dev_pitch) is True
    reason = SignalDetectionEngine.classify_disqualification(dev_pitch)
    assert "Developer advertising" in reason or "Freelancer" in reason or "Competitor" in reason

    # Job seeker
    job_seeker = "Actively seeking a developer position. Resume and CV available. #opentowork"
    assert SignalDetectionEngine.check_false_positive(job_seeker) is True
    reason = SignalDetectionEngine.classify_disqualification(job_seeker)
    assert "Job seeker" in reason

    # Explicit buyer requesting a website
    buyer_request = "Looking for someone to build a website for my new boutique brand next week."
    assert SignalDetectionEngine.check_false_positive(buyer_request) is False
    signals = SignalDetectionEngine.detect_signals(buyer_request)
    assert len(signals) > 0
    assert SignalDetectionEngine.has_explicit_intent(signals) is True


# ==============================================================================
# DEFECT 5: Extracted Threads text cleans UI artifacts
# ==============================================================================
def test_defect_5_clean_threads_ui_artifacts():
    """Verify Follow, Like, Reply, Repost, Share and audio indicators are cleanly removed."""
    raw_sample = 'Followibrahim.aminu0110/02/26More@ibrahim.aminu01 \nNEED A WEBSITE DESIGNER \nBUDGET: $2000 1/2Like3Reply10RepostShare'
    cleaned = clean_social_post_text(raw_sample, author_hint="ibrahim.aminu01")
    assert "Follow" not in cleaned
    assert "Like" not in cleaned
    assert "Reply" not in cleaned
    assert "Repost" not in cleaned
    assert "Share" not in cleaned
    assert "More" not in cleaned
    assert "NEED A WEBSITE DESIGNER" in cleaned
    assert "$2000" in cleaned

    sample2 = 'Followcyrickkyle1hMoreHi everyone, looking for a web developer to revamp our site. Like5Reply2RepostShare'
    cleaned2 = clean_social_post_text(sample2, author_hint="cyrickkyle")
    assert cleaned2.startswith("Hi everyone")
    assert "Like" not in cleaned2
    assert "Repost" not in cleaned2

    sample_audio = 'Audio is muted\nLooking for an app developer to build an iOS app. Like Reply Share'
    cleaned_audio = clean_social_post_text(sample_audio)
    assert "Audio is muted" not in cleaned_audio
    assert "Like" not in cleaned_audio
    assert "Looking for an app developer to build an iOS app." in cleaned_audio


# ==============================================================================
# DEFECT 6: Dashboard feed provides real post URL, date, and country evidence
# ==============================================================================
@pytest.mark.asyncio
async def test_defect_6_dashboard_feed_structure():
    """Verify dashboard feed endpoint fields and metric calculations."""
    from services.api.app.api.v1.routes.prospecting import get_dashboard_feed
    from services.api.app.models.prospecting import ProspectCandidate
    mock_db = AsyncMock()

    c1 = ProspectCandidate(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        platform="THREADS",
        username_or_handle="@real_buyer",
        company_name="Real Buyer",
        domain=None,
        source_url="https://www.threads.com/@real_buyer/post/xyz123",
        canonical_url="https://www.threads.com/@real_buyer/post/xyz123",
        discovery_evidence="NEED A WEBSITE DESIGNER",
        status=CandidateStatus.QUALIFIED.value,
        confidence=0.95,
        metadata_json={
            "urgency": "HIGH",
            "urgency_reason": "Active project timeline",
            "country": "United States",
            "country_evidence": "TLA + USD pricing",
            "qualification_category": "QUALIFIED",
        }
    )

    mock_res_cands = MagicMock()
    mock_res_cands.scalars.return_value.all.return_value = [c1]

    mock_res_jobs = MagicMock()
    mock_res_jobs.scalars.return_value.all.return_value = []

    mock_db.execute.side_effect = [mock_res_cands, mock_res_jobs]

    # Call get_dashboard_feed
    feed = await get_dashboard_feed(limit=50, db=mock_db, org_id=c1.organization_id)
    assert "metrics" in feed
    assert "prospects" in feed
    assert feed["metrics"]["qualified"] == 1

    prospect = feed["prospects"][0]
    assert prospect["author"] == "@real_buyer"
    assert prospect["source_url"] == "https://www.threads.com/@real_buyer/post/xyz123"
    assert prospect["country"] == "United States"
    assert prospect["country_evidence"] == "TLA + USD pricing"
    assert prospect["status"] == "QUALIFIED"
    assert prospect["website"] is None
