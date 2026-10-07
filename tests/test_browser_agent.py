import uuid
import pytest
from httpx import AsyncClient

from packages.agent_core.tools import BrowserToolRegistry
from packages.shared_types.agent import AgentState, ToolRiskLevel
from services.api.app.agents.browser.state_machine import (
    BrowserAgentStateMachine,
    InvalidStateTransitionError,
)
from services.api.app.agents.discovery.opportunity_detector import OpportunityDetector

ORG_A = "00000000-0000-0000-0000-000000000001"
ORG_B = "00000000-0000-0000-0000-000000000002"


def test_agent_state_machine_lifecycle():
    sm = BrowserAgentStateMachine()
    assert sm.current_state == AgentState.IDLE

    # Transition to OBSERVING
    sm.transition_to(AgentState.OBSERVING)
    assert sm.current_state == AgentState.OBSERVING

    # Pause and Resume
    sm.pause()
    assert sm.current_state == AgentState.PAUSED
    sm.resume()
    assert sm.current_state == AgentState.OBSERVING

    # Trigger BLOCKED state
    sm.block()
    assert sm.current_state == AgentState.BLOCKED


def test_agent_state_machine_invalid_transition_rejected():
    sm = BrowserAgentStateMachine()
    # Direct transition from IDLE to EXECUTING is invalid
    with pytest.raises(InvalidStateTransitionError):
        sm.transition_to(AgentState.EXECUTING)


def test_browser_tool_registry():
    assert BrowserToolRegistry.is_valid_tool("open_page") is True
    assert BrowserToolRegistry.is_valid_tool("read_page") is True
    assert BrowserToolRegistry.is_valid_tool("request_user_approval") is True
    assert BrowserToolRegistry.is_valid_tool("stealth_cookie_scraper") is False

    approval_tool = BrowserToolRegistry.get("request_user_approval")
    assert approval_tool.requires_approval is True
    assert approval_tool.risk_level == ToolRiskLevel.HIGH


def test_opportunity_detector_on_instagram_launch():
    caption = "Finally launching my clothing brand next month. Trying to figure out the online store."
    res = OpportunityDetector.evaluate_content(text=caption)
    assert res.is_opportunity is True
    assert res.opportunity_type in ["BUSINESS_LAUNCH", "ECOMMERCE_OPPORTUNITY"]
    assert res.confidence >= 0.85
    assert len(res.evidence) > 0


def test_opportunity_detector_on_reddit_hiring():
    post = "Looking for a web developer to rebuild our agency website with modern stack."
    res = OpportunityDetector.evaluate_content(text=post)
    assert res.is_opportunity is True
    assert res.opportunity_type == "WEBSITE_REQUEST"
    assert res.recommended_service == "Business Website"


def test_opportunity_detector_ignores_irrelevant_content():
    text = "Great sunny day out at the beach with friends! Excited for the weekend."
    res = OpportunityDetector.evaluate_content(text=text)
    assert res.is_opportunity is False


@pytest.mark.asyncio
async def test_browser_agent_session_and_observe_flow(client: AsyncClient):
    headers = {"X-Organization-ID": ORG_A}

    # 1. Start session
    session_payload = {
        "browser_id": "chrome-tab-001",
        "initial_url": "https://www.instagram.com/p/reel123/",
    }
    s_res = await client.post("/api/v1/agent/sessions", json=session_payload, headers=headers)
    assert s_res.status_code == 201
    session_data = s_res.json()
    session_id = session_data["id"]
    assert session_data["current_domain"] == "instagram.com"

    # 2. Record tool execution event
    ev_payload = {
        "event_type": "tool_executed",
        "tool": "read_page",
        "url": "https://www.instagram.com/p/reel123/",
        "input_summary": "Extracted visible Reel caption",
        "output_summary": "Read 120 characters",
    }
    ev_res = await client.post(f"/api/v1/agent/sessions/{session_id}/events", json=ev_payload, headers=headers)
    assert ev_res.status_code == 201

    # 3. Observe page with high-intent launch content
    obs_payload = {
        "url": "https://www.instagram.com/p/reel123/",
        "visible_text": "Launching my clothing brand next month. Need to figure out the online store.",
        "recipient_handle": "@brand_founder",
        "profile_url": "https://instagram.com/brand_founder",
    }
    obs_res = await client.post(f"/api/v1/agent/sessions/{session_id}/observe", json=obs_payload, headers=headers)
    assert obs_res.status_code == 200
    obs_data = obs_res.json()
    assert obs_data["is_opportunity"] is True
    assert obs_data["approval_id"] is not None
    assert obs_data["approval_status"] == "PENDING"
    assert "launch" in obs_data["draft_content"].lower()
    approval_id = obs_data["approval_id"]

    # 4. Attempt to execute while still PENDING -> Must be rejected (403)
    unapproved_res = await client.post(f"/api/v1/agent/approvals/{approval_id}/execute", headers=headers)
    assert unapproved_res.status_code == 403

    # 5. Sahil approves the message
    review_payload = {"decision": "APPROVED", "reviewer": "Sahil"}
    rev_res = await client.post(f"/api/v1/agent/approvals/{approval_id}/review", json=review_payload, headers=headers)
    assert rev_res.status_code == 200
    assert rev_res.json()["status"] == "APPROVED"

    # 6. Execute approved action -> Succeeds and marks EXECUTED
    exec_res = await client.post(f"/api/v1/agent/approvals/{approval_id}/execute", headers=headers)
    assert exec_res.status_code == 200
    assert exec_res.json()["status"] == "EXECUTED"

    # 7. Duplicate Contact Protection: Attempting another outreach to same recipient must fail
    dup_obs = {
        "url": "https://www.instagram.com/p/another_reel/",
        "visible_text": "Need website redesign for our new collection launch.",
        "recipient_handle": "@brand_founder",
        "profile_url": "https://instagram.com/brand_founder",
    }
    # Second observation will fail to create an approval because recipient is already contacted
    dup_res = await client.post(f"/api/v1/agent/sessions/{session_id}/observe", json=dup_obs, headers=headers)
    # The duplicate check in request_action_approval raises ActionBlockedException, returning 403 Forbidden
    assert dup_res.status_code == 403
    assert "already been contacted" in dup_res.json()["detail"]


@pytest.mark.asyncio
async def test_agent_multi_tenancy_isolation(client: AsyncClient):
    # Org A creates session
    s_res = await client.post(
        "/api/v1/agent/sessions",
        json={"browser_id": "chrome-tab-org-a"},
        headers={"X-Organization-ID": ORG_A},
    )
    assert s_res.status_code == 201
    org_a_session_id = s_res.json()["id"]

    # Org B attempts to access Org A's session directly
    sec_res = await client.get(
        f"/api/v1/agent/sessions/{org_a_session_id}",
        headers={"X-Organization-ID": ORG_B},
    )
    assert sec_res.status_code == 404
