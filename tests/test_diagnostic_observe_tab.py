import asyncio
import uuid
import pytest
from datetime import datetime, timezone
from services.api.app.agents.browser.gateway import browser_gateway
from services.api.app.services.event_dispatcher import EventDispatcher

@pytest.mark.asyncio
async def test_observe_tab_flow_with_example_com():
    """
    Controlled Diagnostic:
    Verify the complete backend flow when an OBSERVATION frame
    extracted from https://example.com/ is sent over WebSocket to FastAPI.
    """
    session_id = uuid.uuid4()
    org_id = uuid.uuid4()

    EventDispatcher.clear_events()

    try:
        # Register active session and org in browser gateway
        browser_gateway._session_orgs[session_id] = org_id

        # Exact observation payload extracted by extension from https://example.com/
        observation_payload = {
            "url": "https://example.com/",
            "title": "Example Domain",
            "origin": "https://example.com",
            "page_type": "PUBLIC_WEBSITE",
            "visible_text": "Example Domain\nThis domain is for use in illustrative examples in documents.",
            "headings": ["Example Domain"],
            "links": ["https://www.iana.org/domains/example"],
            "recipient_handle": None,
            "profile_url": None,
            "meta_description": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Simulate incoming WebSocket frame from extension
        await browser_gateway.handle_incoming_frame(
            session_id=session_id,
            frame={
                "frame_type": "OBSERVATION",
                "payload": observation_payload,
            },
        )

        # Verify event was dispatched into EventDispatcher audit log
        events = EventDispatcher.get_recent_events("browser.observation.created")
        assert len(events) == 1
        event = events[0]
        assert event["event_type"] == "browser.observation.created"
        assert event["organization_id"] == str(org_id)
        assert event["payload"]["session_id"] == str(session_id)
        assert event["payload"]["url"] == "https://example.com/"
        assert event["payload"]["title"] == "Example Domain"
        assert event["payload"]["page_type"] == "PUBLIC_WEBSITE"
        assert "Example Domain" in event["payload"]["visible_text_snippet"]

    finally:
        browser_gateway._session_orgs.pop(session_id, None)
