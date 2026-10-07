import asyncio
import time
import uuid
import pytest
from httpx import AsyncClient
from starlette.testclient import TestClient

from packages.shared_types.agent import SessionStatus
from packages.shared_types.browser_protocol import (
    BrowserCommand,
    BrowserCommandType,
    CommandExecutionStatus,
    ExtensionSessionState,
    PageType,
)
from packages.shared_types.outreach import DraftStatus, OutreachChannel
from services.api.app.agents.browser.gateway import (
    browser_gateway,
)
from services.api.app.main import app
from services.api.app.models.agent import AgentSession
from services.api.app.models.crm import Lead
from services.api.app.models.outreach import OutreachDraft
from services.api.app.repositories.outreach import OutreachRepository

ORG_A = uuid.UUID("00000000-0000-0000-0000-000000000001")
ORG_B = uuid.UUID("00000000-0000-0000-0000-000000000002")


# ---------------------------------------------------------------------------
# 1. Pairing Challenge & Authentication Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pairing_challenge_lifecycle(client: AsyncClient):
    headers = {"X-Organization-ID": str(ORG_A)}

    # 1. Generate challenge code
    res = await client.post("/api/v1/agent/browser/challenge", headers=headers)
    assert res.status_code == 200
    challenge = res.json()
    assert "pairing_code" in challenge
    assert challenge["pairing_code"].startswith("TV-")
    code = challenge["pairing_code"]

    # 2. Pair extension with valid code
    pair_payload = {
        "pairing_code": code,
        "browser_id": "test-chrome-agent-001",
        "client_version": "2.0.0",
    }
    pair_res = await client.post("/api/v1/agent/browser/pair", json=pair_payload, headers=headers)
    assert pair_res.status_code == 200
    pair_data = pair_res.json()
    assert "token" in pair_data
    assert pair_data["token"].startswith("tv_sess_")
    assert pair_data["organization_id"] == str(ORG_A)
    session_id = uuid.UUID(pair_data["session_id"])

    # 3. Verify single-use property (re-using code must fail)
    reuse_res = await client.post("/api/v1/agent/browser/pair", json=pair_payload, headers=headers)
    assert reuse_res.status_code == 400

    # 4. Check status
    status_res = await client.get(f"/api/v1/agent/browser/status?session_id={session_id}", headers=headers)
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["session_id"] == str(session_id)
    assert status_data["organization_id"] == str(ORG_A)


@pytest.mark.asyncio
async def test_session_controls_pause_resume_stop(client: AsyncClient, test_db_session):
    headers = {"X-Organization-ID": str(ORG_A)}

    # Create session
    ch = browser_gateway.create_pairing_challenge(ORG_A)
    pair = browser_gateway.verify_and_pair(
        pairing_code=ch["pairing_code"],
        session_id=uuid.uuid4(),
        browser_id="browser-control-test",
    )
    sess_id = pair["session_id"]

    # Also persist in DB
    db_sess = AgentSession(
        id=sess_id,
        organization_id=ORG_A,
        browser_id="browser-control-test",
        status=SessionStatus.RUNNING.value,
    )
    test_db_session.add(db_sess)
    await test_db_session.commit()

    # 1. Pause
    pause_res = await client.post(
        "/api/v1/agent/browser/pause",
        json={"session_id": str(sess_id), "reason": "Testing pause"},
        headers=headers,
    )
    assert pause_res.status_code == 200
    assert pause_res.json()["status"] == "PAUSED"

    # 2. Resume
    resume_res = await client.post(
        "/api/v1/agent/browser/resume",
        json={"session_id": str(sess_id), "reason": "Testing resume"},
        headers=headers,
    )
    assert resume_res.status_code == 200
    assert resume_res.json()["status"] == "RUNNING"

    # 3. Stop
    stop_res = await client.post(
        "/api/v1/agent/browser/stop",
        json={"session_id": str(sess_id), "reason": "Testing stop"},
        headers=headers,
    )
    assert stop_res.status_code == 200
    assert stop_res.json()["status"] == "STOPPED"


# ---------------------------------------------------------------------------
# 2. WebSocket Gateway Connection Tests
# ---------------------------------------------------------------------------
def test_websocket_connection_unauthorized():
    from starlette.websockets import WebSocketDisconnect
    sync_client = TestClient(app)

    # Missing token -> 4001
    with sync_client.websocket_connect("/api/v1/agent/browser/ws") as ws:
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
        assert exc.value.code == 4001

    # Invalid token -> 4003
    with sync_client.websocket_connect("/api/v1/agent/browser/ws?token=invalid_token_xyz") as ws:
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
        assert exc.value.code == 4003


@pytest.mark.asyncio
async def test_websocket_connection_lifecycle_and_frames():
    sync_client = TestClient(app)

    # 1. Set up session and token
    ch = browser_gateway.create_pairing_challenge(ORG_A)
    sess_id = uuid.uuid4()
    pair = browser_gateway.verify_and_pair(
        pairing_code=ch["pairing_code"],
        session_id=sess_id,
        browser_id="ws-test-browser",
    )
    token = pair["token"]

    # 2. Connect via WebSocket
    with sync_client.websocket_connect(f"/api/v1/agent/browser/ws?token={token}") as ws:
        # Expect CONNECTED_ACK frame
        ack = ws.receive_json()
        assert ack["frame_type"] == "CONNECTED_ACK"
        assert ack["payload"]["session_id"] == str(sess_id)
        assert browser_gateway.is_connected(sess_id) is True

        # Process PAGE_STATE frame directly on gateway
        await browser_gateway.handle_incoming_frame(
            session_id=sess_id,
            frame={
                "frame_type": "PAGE_STATE",
                "payload": {
                    "url": "https://www.instagram.com/p/test1234/",
                    "title": "Apex Luxury Wear on Instagram",
                    "origin": "https://www.instagram.com",
                    "page_type": "INSTAGRAM_POST",
                    "is_loading": False,
                    "visible_text_available": True,
                    "interactive_elements_count": 15,
                    "timestamp": "2026-10-07T12:00:00Z",
                },
            },
        )
        page_state = browser_gateway.get_page_state(sess_id)
        assert page_state is not None
        assert page_state.url == "https://www.instagram.com/p/test1234/"
        assert page_state.page_type == PageType.INSTAGRAM_POST

        # Process SECURITY_ALERT frame directly on gateway
        await browser_gateway.handle_incoming_frame(
            session_id=sess_id,
            frame={
                "frame_type": "SECURITY_ALERT",
                "payload": {
                    "url": "https://www.instagram.com/challenge/",
                    "challenge_type": "CAPTCHA",
                    "reason": "Recaptcha element observed",
                },
            },
        )
        assert browser_gateway.get_session_state(sess_id) == ExtensionSessionState.BLOCKED

    # After exit, session is disconnected
    assert browser_gateway.is_connected(sess_id) is False


# ---------------------------------------------------------------------------
# 3. SSRF & Command Validation Security Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_command_ssrf_protection():
    sess_id = uuid.uuid4()
    # Mock registration
    browser_gateway._active_connections[sess_id] = "mock_ws"  # type: ignore
    browser_gateway._session_orgs[sess_id] = ORG_A

    try:
        # Loopback URL
        cmd_loopback = BrowserCommand(
            session_id=sess_id,
            type=BrowserCommandType.OPEN_PAGE,
            payload={"url": "http://127.0.0.1:8000/internal"},
        )
        res_loopback = await browser_gateway.send_command(cmd_loopback)
        assert res_loopback.success is False
        assert res_loopback.status == CommandExecutionStatus.BLOCKED

        # Cloud Metadata URL
        cmd_metadata = BrowserCommand(
            session_id=sess_id,
            type=BrowserCommandType.OPEN_PAGE,
            payload={"url": "http://169.254.169.254/latest/meta-data"},
        )
        res_metadata = await browser_gateway.send_command(cmd_metadata)
        assert res_metadata.success is False
        assert res_metadata.status == CommandExecutionStatus.BLOCKED

        # Browser Internal Scheme
        cmd_scheme = BrowserCommand(
            session_id=sess_id,
            type=BrowserCommandType.OPEN_PAGE,
            payload={"url": "chrome://settings"},
        )
        res_scheme = await browser_gateway.send_command(cmd_scheme)
        assert res_scheme.success is False
        assert res_scheme.status == CommandExecutionStatus.BLOCKED

    finally:
        browser_gateway._active_connections.pop(sess_id, None)
        browser_gateway._session_orgs.pop(sess_id, None)


# ---------------------------------------------------------------------------
# 4. Approval-Gated Outreach Execution Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_execute_approved_outreach_flow(client: AsyncClient, test_db_session):
    headers = {"X-Organization-ID": str(ORG_A)}
    sess_id = uuid.uuid4()
    lead_id = uuid.uuid4()
    draft_id = uuid.uuid4()

    # Create Lead
    lead = Lead(
        id=lead_id,
        organization_id=ORG_A,
        title="Apex Luxury Wear",
        overall_score=86,
        recommended_service="ECOMMERCE",
    )
    test_db_session.add(lead)

    # 1. Draft is in DRAFT status (unapproved)
    draft_unapproved = OutreachDraft(
        id=draft_id,
        organization_id=ORG_A,
        lead_id=lead_id,
        channel="INSTAGRAM_DM",
        body="Hey, noticed you're launching Apex Luxury Wear...",
        angle="ECOMMERCE",
        recommended_service="ECOMMERCE",
        status=DraftStatus.DRAFT.value,
        metadata_json={"recipient": "@apexluxury"},
    )
    test_db_session.add(draft_unapproved)
    await test_db_session.commit()

    # Attempt execution -> must be rejected (not APPROVED)
    exec_payload = {
        "session_id": str(sess_id),
        "lead_id": str(lead_id),
        "draft_id": str(draft_id),
    }
    unapp_res = await client.post(
        "/api/v1/agent/browser/execute-approved-outreach",
        json=exec_payload,
        headers=headers,
    )
    assert unapp_res.status_code == 400
    assert "must be APPROVED" in unapp_res.json()["detail"]

    # 2. Update draft to APPROVED status
    draft_unapproved.status = DraftStatus.APPROVED.value
    await test_db_session.commit()

    # Extension not connected -> 412 PRECONDITION_FAILED
    not_conn_res = await client.post(
        "/api/v1/agent/browser/execute-approved-outreach",
        json=exec_payload,
        headers=headers,
    )
    assert not_conn_res.status_code == 412

    # 3. Connect extension mock and test successful execution
    class MockWebSocket:
        def __init__(self):
            self.sent_frames = []

        async def send_json(self, frame):
            self.sent_frames.append(frame)
            # Simulate extension returning immediate success result
            cmd = frame["command"]
            asyncio.create_task(
                browser_gateway.handle_incoming_frame(
                    session_id=sess_id,
                    frame={
                        "frame_type": "RESULT",
                        "payload": {
                            "command_id": cmd["command_id"],
                            "success": True,
                            "status": "SUCCESS",
                            "result": {"confirmed": True},
                            "correlation_id": cmd["correlation_id"],
                        },
                    },
                )
            )

    mock_ws = MockWebSocket()
    browser_gateway._active_connections[sess_id] = mock_ws  # type: ignore
    browser_gateway._session_orgs[sess_id] = ORG_A

    try:
        success_res = await client.post(
            "/api/v1/agent/browser/execute-approved-outreach",
            json=exec_payload,
            headers=headers,
        )
        assert success_res.status_code == 200
        data = success_res.json()
        assert data["success"] is True
        assert data["status"] == "SENT"
        assert "attempt_id" in data

        # 4. Duplicate prevention test: attempting second send -> 409 CONFLICT
        dup_res = await client.post(
            "/api/v1/agent/browser/execute-approved-outreach",
            json=exec_payload,
            headers=headers,
        )
        assert dup_res.status_code == 409
        assert "Outreach already sent" in dup_res.json()["detail"]

    finally:
        browser_gateway._active_connections.pop(sess_id, None)
        browser_gateway._session_orgs.pop(sess_id, None)


# ---------------------------------------------------------------------------
# 5. Uncertain Delivery Protection Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_uncertain_delivery_protection(client: AsyncClient, test_db_session):
    headers = {"X-Organization-ID": str(ORG_A)}
    sess_id = uuid.uuid4()
    lead_id = uuid.uuid4()
    draft_id = uuid.uuid4()

    lead = Lead(
        id=lead_id,
        organization_id=ORG_A,
        title="Boutique Trends",
        overall_score=80,
        recommended_service="ECOMMERCE",
    )
    draft = OutreachDraft(
        id=draft_id,
        organization_id=ORG_A,
        lead_id=lead_id,
        channel="REDDIT_REPLY",
        body="Have you considered improving your store navigation?",
        angle="ECOMMERCE",
        recommended_service="ECOMMERCE",
        status=DraftStatus.APPROVED.value,
        metadata_json={"recipient": "u/boutique_owner"},
    )
    test_db_session.add(lead)
    test_db_session.add(draft)
    await test_db_session.commit()

    # Mock extension returning DELIVERY_UNKNOWN
    class MockUncertainWebSocket:
        async def send_json(self, frame):
            cmd = frame["command"]
            asyncio.create_task(
                browser_gateway.handle_incoming_frame(
                    session_id=sess_id,
                    frame={
                        "frame_type": "RESULT",
                        "payload": {
                            "command_id": cmd["command_id"],
                            "success": False,
                            "status": "DELIVERY_UNKNOWN",
                            "error": "DOM mutated unexpectedly; could not verify post submission",
                            "correlation_id": cmd["correlation_id"],
                        },
                    },
                )
            )

    browser_gateway._active_connections[sess_id] = MockUncertainWebSocket()  # type: ignore
    browser_gateway._session_orgs[sess_id] = ORG_A

    try:
        res = await client.post(
            "/api/v1/agent/browser/execute-approved-outreach",
            json={"session_id": str(sess_id), "lead_id": str(lead_id), "draft_id": str(draft_id)},
            headers=headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is False
        assert data["status"] == "DELIVERY_UNKNOWN"

        # Verify draft marked for review and not retried
        repo = OutreachRepository(test_db_session)
        updated_draft = await repo.get_draft(ORG_A, draft_id)
        assert updated_draft.status == DraftStatus.NEEDS_REVIEW.value

    finally:
        browser_gateway._active_connections.pop(sess_id, None)
        browser_gateway._session_orgs.pop(sess_id, None)


# ---------------------------------------------------------------------------
# 6. Multi-Tenant Isolation Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_browser_gateway_multi_tenant_isolation(client: AsyncClient, test_db_session):
    # Setup session under Org A
    ch = browser_gateway.create_pairing_challenge(ORG_A)
    pair = browser_gateway.verify_and_pair(
        pairing_code=ch["pairing_code"],
        session_id=uuid.uuid4(),
        browser_id="multi-tenant-test",
    )
    sess_id = pair["session_id"]

    db_sess = AgentSession(
        id=sess_id,
        organization_id=ORG_A,
        browser_id="multi-tenant-test",
        status=SessionStatus.RUNNING.value,
    )
    test_db_session.add(db_sess)
    await test_db_session.commit()

    # Org B attempts to inspect Org A's session -> must return 404
    headers_org_b = {"X-Organization-ID": str(ORG_B)}
    res = await client.get(f"/api/v1/agent/browser/status?session_id={sess_id}", headers=headers_org_b)
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# 7. End-to-End Product Flow Test
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_end_to_end_browser_agent_flow(client: AsyncClient, test_db_session):
    headers = {"X-Organization-ID": str(ORG_A)}

    # Step 1: User requests pairing challenge in TechVerse dashboard
    ch_res = await client.post("/api/v1/agent/browser/challenge", headers=headers)
    assert ch_res.status_code == 200
    pairing_code = ch_res.json()["pairing_code"]

    # Step 2: Chrome extension pairs and receives session credentials
    pair_res = await client.post(
        "/api/v1/agent/browser/pair",
        json={"pairing_code": pairing_code, "browser_id": "e2e-chrome-agent", "client_version": "2.0.0"},
        headers=headers,
    )
    assert pair_res.status_code == 200
    sess_id = uuid.UUID(pair_res.json()["session_id"])

    # Step 3: Browser extension observes Instagram post
    obs_url = "https://www.instagram.com/p/DFtest789/"
    obs_text = "Looking for a website developer to build our online store and fix mobile checkout friction."
    obs_res = await client.post(
        f"/api/v1/agent/sessions/{sess_id}/observe",
        json={
            "url": obs_url,
            "visible_text": obs_text,
            "recipient_handle": "@apexluxurywear",
            "profile_url": "https://www.instagram.com/apexluxurywear/",
        },
        headers=headers,
    )
    assert obs_res.status_code == 200
    lead_id_str = obs_res.json().get("lead_id")
    assert lead_id_str is not None
    lead_id = uuid.UUID(lead_id_str)

    # Step 4: Phase 3 signals and scoring
    signals_res = await client.post(
        f"/api/v1/leads/{lead_id}/signals/analyze",
        json={"text": obs_text, "source_url": obs_url},
        headers=headers,
    )
    assert signals_res.status_code == 200

    score_res = await client.post(f"/api/v1/leads/{lead_id}/score", headers=headers)
    assert score_res.status_code == 200
    assert score_res.json()["overall_score"] >= 50

    # Step 5: Phase 5 personalized outreach generation
    gen_res = await client.post(
        f"/api/v1/leads/{lead_id}/outreach/generate",
        json={"channel": "INSTAGRAM_DM"},
        headers=headers,
    )
    assert gen_res.status_code == 201
    drafts_list = gen_res.json()
    assert len(drafts_list) >= 1
    draft_data = drafts_list[0]
    draft_id = uuid.UUID(draft_data["id"])
    assert draft_data["quality_score"] >= 75
    assert draft_data["status"] == "READY_FOR_APPROVAL"

    # Step 6: Human review and approval gate (transitions to APPROVED)
    appr_res = await client.post(
        f"/api/v1/leads/{lead_id}/outreach/{draft_id}/approve",
        json={"reviewer": "Sahil", "decision_reason": "Verified accurate mobile friction evidence"},
        headers=headers,
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "APPROVED"

    # Step 7: Extension executes approved outreach action
    class MockE2EExtensionWS:
        async def send_json(self, frame):
            cmd = frame["command"]
            assert cmd["type"] == "EXECUTE_APPROVED_OUTREACH"
            assert cmd["payload"]["recipient"] == "@apexluxurywear"
            # Simulate user confirmation in popup
            asyncio.create_task(
                browser_gateway.handle_incoming_frame(
                    session_id=sess_id,
                    frame={
                        "frame_type": "RESULT",
                        "payload": {
                            "command_id": cmd["command_id"],
                            "success": True,
                            "status": "SUCCESS",
                            "result": {"user_confirmed": True, "executed": True},
                            "correlation_id": cmd["correlation_id"],
                        },
                    },
                )
            )

    browser_gateway._active_connections[sess_id] = MockE2EExtensionWS()  # type: ignore
    browser_gateway._session_orgs[sess_id] = ORG_A

    try:
        exec_res = await client.post(
            "/api/v1/agent/browser/execute-approved-outreach",
            json={"session_id": str(sess_id), "lead_id": str(lead_id), "draft_id": str(draft_id)},
            headers=headers,
        )
        assert exec_res.status_code == 200
        exec_data = exec_res.json()
        assert exec_data["success"] is True
        assert exec_data["status"] == "SENT"
        assert "attempt_id" in exec_data

        # Verify draft in DB is SENT
        repo = OutreachRepository(test_db_session)
        final_draft = await repo.get_draft(ORG_A, draft_id)
        assert final_draft.status == DraftStatus.SENT.value

        # Verify attempt recorded
        attempts = await repo.get_attempts_for_lead(ORG_A, lead_id)
        assert len(attempts) >= 1
        assert attempts[0].status == "SENT"
    finally:
        browser_gateway._active_connections.pop(sess_id, None)
        browser_gateway._session_orgs.pop(sess_id, None)

