import pytest
import uuid
from packages.shared_types.crm import SignalType
from services.api.app.agents.signals.urgency import UrgencyDetector, UrgencyLevel
from services.api.app.agents.signals.engine import SignalDetectionEngine
from services.api.app.agents.prospecting.sources.threads import ThreadsSource
from services.api.app.services.event_dispatcher import EventDispatcher


def test_urgency_detection_classifications():
    # 1. CRITICAL
    res_crit = UrgencyDetector.evaluate("We need an AI automation system ASAP! Ready to start today.")
    assert res_crit.level == UrgencyLevel.CRITICAL
    assert res_crit.score >= 90
    assert "asap" in res_crit.evidence.lower() or "today" in res_crit.evidence.lower()

    # 2. HIGH
    res_high = UrgencyDetector.evaluate("Launching next week and need someone to build our website.")
    assert res_high.level == UrgencyLevel.HIGH
    assert res_high.score >= 80
    assert "next week" in res_high.evidence.lower() or "launch" in res_high.evidence.lower()

    # 3. MEDIUM
    res_med = UrgencyDetector.evaluate("Planning for next month to revamp our web app.")
    assert res_med.level == UrgencyLevel.MEDIUM
    assert "next month" in res_med.evidence.lower()

    # 4. LOW
    res_low = UrgencyDetector.evaluate("Thinking about redesigning our landing page down the road, no rush.")
    assert res_low.level == UrgencyLevel.LOW

    # 5. NONE
    res_none = UrgencyDetector.evaluate("We are a fintech company operating in Austin.")
    assert res_none.level == UrgencyLevel.NONE
    assert res_none.evidence is None


def test_false_positive_filtering():
    # Student / Homework -> Disqualified
    assert SignalDetectionEngine.check_false_positive("Need help with my homework project for college cs class") is True
    # Job seeker -> Disqualified
    assert SignalDetectionEngine.check_false_positive("Here is my resume, looking for a job as a developer") is True
    # Competitor agency -> Disqualified
    assert SignalDetectionEngine.check_false_positive("Our agency offers web design and seo services, dm us") is True
    # Freelancer seeking clients -> Disqualified
    assert SignalDetectionEngine.check_false_positive("I am a freelance web developer available for clients") is True

    # Real commercial buyer -> NOT disqualified
    assert SignalDetectionEngine.check_false_positive("We are launching our fintech SaaS and need someone to build our landing page") is False


def test_threads_source_structured_posts_discovery():
    adapter = ThreadsSource()
    obs = {
        "url": "https://www.threads.net/",
        "visible_text": "Sample visible threads stream",
        "content_units": [
            {
                "author": "@austinfintech",
                "text": "Looking for someone to build our website and marketing landing page. Launching next month! Visit finflowhq.com",
                "url": "https://www.threads.net/@austinfintech/post/123",
                "links": ["https://finflowhq.com"]
            }
        ]
    }
    items = adapter.discover_candidates(obs)
    assert len(items) == 1
    item = items[0]
    assert item.username_or_handle == "@austinfintech"
    assert item.domain == "finflowhq.com"
    assert "build our website" in item.evidence

    dedup = adapter.build_dedup_key(item)
    assert dedup == "threads:austinfintech"


@pytest.mark.asyncio
async def test_real_time_event_contract():
    EventDispatcher.clear_events()
    org_id = uuid.uuid4()
    job_id = uuid.uuid4()
    session_id = uuid.uuid4()
    cand_id = uuid.uuid4()
    lead_id = uuid.uuid4()

    received_events = []
    def _subscriber(evt):
        received_events.append(evt)

    EventDispatcher.subscribe(_subscriber)

    payload = {
        "candidate_id": str(cand_id),
        "lead_id": str(lead_id),
        "platform": "THREADS",
        "author": "@austinfintech",
        "source_url": "https://www.threads.net/@austinfintech",
        "evidence": "Looking for someone to build our website. Launching next month.",
        "score": 88,
        "intent_score": 90,
        "urgency": "HIGH",
        "urgency_reason": "Product launch scheduled in near term ('launching next month').",
        "service_match": "Business Website",
        "website": "finflowhq.com",
        "created_at": "2026-10-08T14:00:00Z",
        "status": "READY_FOR_APPROVAL",
    }

    event = await EventDispatcher.dispatch(
        event_type="PROSPECT_DISCOVERED",
        data=payload,
        organization_id=org_id,
        lead_id=lead_id,
        job_id=job_id,
        session_id=session_id,
    )

    EventDispatcher.unsubscribe(_subscriber)

    assert event["event_type"] == "PROSPECT_DISCOVERED"
    assert event["job_id"] == str(job_id)
    assert event["session_id"] == str(session_id)
    assert event["payload"]["urgency"] == "HIGH"
    assert event["payload"]["status"] == "READY_FOR_APPROVAL"
    assert len(received_events) == 1
    assert received_events[0]["event_id"] == event["event_id"]
