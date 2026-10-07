import asyncio
import logging
import uuid
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared_types.agent import AgentState, SessionStatus
from packages.shared_types.browser_protocol import (
    BrowserCommand,
    BrowserCommandResult,
    BrowserCommandType,
    CommandExecutionStatus,
    ExtensionSessionState,
)
from packages.shared_types.outreach import DraftStatus
from services.api.app.agents.browser.gateway import (
    BrowserGatewayException,
    browser_gateway,
)
from services.api.app.api.v1.dependencies.auth import get_current_org_id
from services.api.app.core.database import get_db
from services.api.app.models.agent import AgentEvent, AgentSession
from services.api.app.models.outreach import OutreachApproval, OutreachAttempt, OutreachDraft
from services.api.app.repositories.crm import CompanyRepository, ContactRepository, LeadRepository, OrganizationRepository
from services.api.app.repositories.outreach import OutreachRepository
from services.api.app.schemas.browser_gateway import (
    BrowserStatusResponse,
    ExecuteApprovedOutreachRequest,
    PairingChallengeResponse,
    PairRequest,
    PairResponse,
    RevokeRequest,
    SessionControlRequest,
)
from services.api.app.services.agent_service import AgentService, AgentServiceException
from services.api.app.services.event_dispatcher import EventDispatcher

logger = logging.getLogger("techverse.api.routes.browser_gateway")

router = APIRouter(prefix="/agent/browser", tags=["Browser Gateway"])


@router.post("/challenge", response_model=PairingChallengeResponse)
async def generate_pairing_challenge(
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> PairingChallengeResponse:
    """Generate a short-lived single-use pairing challenge code for Chrome extension pairing."""
    challenge = browser_gateway.create_pairing_challenge(org_id=org_id, ttl_seconds=300)
    return PairingChallengeResponse(**challenge)


@router.post("/pair", response_model=PairResponse)
async def pair_browser_extension(
    data: PairRequest,
    db: AsyncSession = Depends(get_db),
) -> PairResponse:
    """Verify pairing code submitted by extension, create session if needed, and issue session token."""
    code = data.pairing_code.strip().upper()
    pairing_info = browser_gateway._pairing_challenges.get(code)
    if not pairing_info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired pairing code",
        )

    org_id = pairing_info["organization_id"]
    user_id = pairing_info.get("user_id")

    # Verify organization exists in the database
    org_repo = OrganizationRepository(db)
    org = await org_repo.get_by_id(org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization {org_id} not found or unavailable",
        )

    # If session_id provided, verify or create session
    session_id = data.session_id
    if not session_id:
        try:
            agent_service = AgentService(db)
            new_session = await agent_service.create_session(
                org_id=org_id,
                browser_id=data.browser_id,
                user_id=user_id,
                metadata={"client_version": data.client_version},
            )
            session_id = new_session.id
        except Exception as e:
            logger.error("Failed to create agent session during pairing", error=str(e), exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to initialize browser session: {str(e)}",
            )
    else:
        # Check session exists in organization
        stmt = select(AgentSession).where(
            AgentSession.id == session_id,
            AgentSession.organization_id == org_id,
        )
        res = await db.execute(stmt)
        sess = res.scalar_one_or_none()
        if not sess:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found in this organization",
            )

    try:
        pair_result = browser_gateway.verify_and_pair(
            pairing_code=data.pairing_code,
            session_id=session_id,
            browser_id=data.browser_id,
            client_version=data.client_version,
        )
        return PairResponse(**pair_result)
    except BrowserGatewayException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/revoke")
async def revoke_browser_session(
    data: RevokeRequest,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> Dict[str, Any]:
    """Revoke browser session token and stop pending browser actions."""
    stmt = select(AgentSession).where(
        AgentSession.id == data.session_id,
        AgentSession.organization_id == org_id,
    )
    res = await db.execute(stmt)
    sess = res.scalar_one_or_none()
    if not sess:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {data.session_id} not found",
        )

    browser_gateway.revoke_session(data.session_id)
    sess.status = SessionStatus.COMPLETED.value
    await db.commit()

    return {"revoked": True, "session_id": str(data.session_id)}


@router.get("/status", response_model=BrowserStatusResponse)
async def get_browser_status(
    session_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> BrowserStatusResponse:
    """Inspect active browser extension connection status and page state."""
    if session_id:
        stmt = select(AgentSession).where(
            AgentSession.id == session_id,
            AgentSession.organization_id == org_id,
        )
        res = await db.execute(stmt)
        sess = res.scalar_one_or_none()
        if not sess:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

        is_conn = browser_gateway.is_connected(session_id)
        state_enum = browser_gateway.get_session_state(session_id)
        page_state = browser_gateway.get_page_state(session_id)

        return BrowserStatusResponse(
            session_id=session_id,
            organization_id=org_id,
            is_connected=is_conn,
            session_state=state_enum.value,
            current_url=page_state.url if page_state else sess.current_url,
            current_domain=page_state.origin if page_state else sess.current_domain,
            page_type=page_state.page_type.value if page_state else None,
        )

    return BrowserStatusResponse(
        session_id=None,
        organization_id=org_id,
        is_connected=False,
        session_state=ExtensionSessionState.DISCONNECTED.value,
    )


@router.post("/pause")
async def pause_browser_session(
    data: SessionControlRequest,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> Dict[str, Any]:
    """Pause operations on the active browser agent session."""
    agent_service = AgentService(db)
    try:
        sess = await agent_service.get_session(org_id, data.session_id)
    except AgentServiceException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {data.session_id} not found",
        )

    sess.status = SessionStatus.PAUSED.value
    await db.commit()

    # Send PAUSE command to extension if connected
    if browser_gateway.is_connected(data.session_id):
        cmd = BrowserCommand(
            session_id=data.session_id,
            type=BrowserCommandType.PAUSE,
            payload={"reason": data.reason or "User paused session"},
        )
        await browser_gateway.send_command(cmd, timeout_seconds=5.0)

    await EventDispatcher.dispatch(
        event_type="browser.session.paused",
        data={"session_id": str(data.session_id), "reason": data.reason},
        organization_id=org_id,
    )
    return {"status": "PAUSED", "session_id": str(data.session_id)}


@router.post("/resume")
async def resume_browser_session(
    data: SessionControlRequest,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> Dict[str, Any]:
    """Resume operations on a paused browser session."""
    agent_service = AgentService(db)
    try:
        sess = await agent_service.get_session(org_id, data.session_id)
    except AgentServiceException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {data.session_id} not found",
        )

    sess.status = SessionStatus.RUNNING.value
    await db.commit()

    if browser_gateway.is_connected(data.session_id):
        cmd = BrowserCommand(
            session_id=data.session_id,
            type=BrowserCommandType.RESUME,
            payload={"reason": data.reason or "User resumed session"},
        )
        await browser_gateway.send_command(cmd, timeout_seconds=5.0)

    await EventDispatcher.dispatch(
        event_type="browser.session.resumed",
        data={"session_id": str(data.session_id), "reason": data.reason},
        organization_id=org_id,
    )
    return {"status": "RUNNING", "session_id": str(data.session_id)}


@router.post("/stop")
async def stop_browser_session(
    data: SessionControlRequest,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> Dict[str, Any]:
    """Stop browser session and cancel pending commands."""
    agent_service = AgentService(db)
    try:
        sess = await agent_service.get_session(org_id, data.session_id)
    except AgentServiceException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {data.session_id} not found",
        )

    sess.status = SessionStatus.COMPLETED.value
    await db.commit()

    if browser_gateway.is_connected(data.session_id):
        cmd = BrowserCommand(
            session_id=data.session_id,
            type=BrowserCommandType.STOP,
            payload={"reason": data.reason or "User stopped session"},
        )
        await browser_gateway.send_command(cmd, timeout_seconds=5.0)

    browser_gateway.revoke_session(data.session_id)

    await EventDispatcher.dispatch(
        event_type="browser.session.stopped",
        data={"session_id": str(data.session_id), "reason": data.reason},
        organization_id=org_id,
    )
    return {"status": "STOPPED", "session_id": str(data.session_id)}


@router.post("/execute-approved-outreach")
async def execute_approved_outreach(
    data: ExecuteApprovedOutreachRequest,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> Dict[str, Any]:
    """
    Execute an approved outreach action via the connected Chrome browser extension.
    Enforces human approval verification, duplicate send prevention, recipient validation,
    and uncertain delivery protection.
    """
    outreach_repo = OutreachRepository(db)

    # 1. Fetch Draft
    draft = await outreach_repo.get_draft(org_id, data.draft_id)
    if not draft or draft.lead_id != data.lead_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Outreach draft not found for this lead",
        )

    # 2. Duplicate outreach protection (already SENT draft or existing sent attempt)
    if draft.status == DraftStatus.SENT.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Outreach already sent: draft has already been executed",
        )

    prior_attempts = await outreach_repo.get_attempts_for_lead(org_id, data.lead_id)
    sent_attempts = [
        a for a in prior_attempts
        if a.channel == draft.channel and a.status in ("SENT", "DELIVERED")
    ]
    if sent_attempts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Outreach already sent to this lead on channel {draft.channel}",
        )

    # 3. Verify Approval Gate (Must be APPROVED)
    if draft.status != DraftStatus.APPROVED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Draft cannot be executed because status is {draft.status}, must be APPROVED",
        )

    # 4. Check active browser connection
    if not browser_gateway.is_connected(data.session_id):
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=f"Browser session {data.session_id} is not connected to Chrome extension",
        )

    # 5. Determine recipient and build EXECUTE_APPROVED_OUTREACH command
    recipient = "Unknown"
    if draft.metadata_json and draft.metadata_json.get("recipient"):
        recipient = str(draft.metadata_json["recipient"])
    else:
        lead_repo = LeadRepository(db)
        lead = await lead_repo.get_by_id(org_id, draft.lead_id)
        if lead:
            if lead.contact_id:
                contact_repo = ContactRepository(db)
                contact = await contact_repo.get_by_id(org_id, lead.contact_id)
                if contact and (contact.handle or contact.email or contact.full_name):
                    recipient = contact.handle or contact.email or contact.full_name
            if recipient == "Unknown" and lead.title and "Discovered via Browser: " in lead.title:
                candidate = lead.title.replace("Discovered via Browser: ", "").strip()
                if candidate.startswith("@"):
                    recipient = candidate
            if recipient == "Unknown" and lead.profile_url:
                import re
                m = re.search(r"instagram\.com/([A-Za-z0-9_.]+)", lead.profile_url)
                if m:
                    recipient = f"@{m.group(1).rstrip('/')}"
                else:
                    recipient = lead.profile_url

    command = BrowserCommand(
        session_id=data.session_id,
        type=BrowserCommandType.EXECUTE_APPROVED_OUTREACH,
        payload={
            "draft_id": str(draft.id),
            "lead_id": str(draft.lead_id),
            "channel": draft.channel,
            "recipient": recipient,
            "subject": draft.subject,
            "body": draft.body,
            "cta_text": draft.cta_text,
            "approval_id": str(data.approval_id) if data.approval_id else None,
        },
    )

    # Dispatch to extension and await user confirmation & execution
    command_result = await browser_gateway.send_command(command, timeout_seconds=30.0)

    # 6. Evaluate Result
    if command_result.status == CommandExecutionStatus.DELIVERY_UNKNOWN:
        # Uncertain delivery protection: record attempt, DO NOT RETRY
        draft.status = DraftStatus.NEEDS_REVIEW.value
        await outreach_repo.record_attempt(
            org_id=org_id,
            lead_id=draft.lead_id,
            channel=draft.channel,
            draft_id=draft.id,
            recipient=command.payload["recipient"],
            status="DELIVERY_UNKNOWN",
            reason=command_result.error or "State changed but delivery confirmation uncertain",
        )
        await db.commit()

        await EventDispatcher.dispatch(
            event_type="outreach.delivery.unknown",
            data={
                "session_id": str(data.session_id),
                "draft_id": str(draft.id),
                "lead_id": str(draft.lead_id),
                "channel": draft.channel,
                "reason": "Uncertain delivery flagged; human review required",
            },
            organization_id=org_id,
        )
        return {
            "success": False,
            "status": "DELIVERY_UNKNOWN",
            "draft_id": str(draft.id),
            "detail": "Action dispatched but confirmation uncertain. Marked for review without retry.",
        }

    elif command_result.success:
        draft.status = DraftStatus.SENT.value
        attempt = await outreach_repo.record_attempt(
            org_id=org_id,
            lead_id=draft.lead_id,
            channel=draft.channel,
            draft_id=draft.id,
            recipient=command.payload["recipient"],
            status="SENT",
            reason="Executed via authorized Chrome browser session",
        )
        await db.commit()

        await EventDispatcher.dispatch(
            event_type="browser.action.executed",
            data={
                "session_id": str(data.session_id),
                "draft_id": str(draft.id),
                "lead_id": str(draft.lead_id),
                "channel": draft.channel,
                "attempt_id": str(attempt.id),
                "timestamp": command_result.timestamp.isoformat(),
            },
            organization_id=org_id,
        )
        return {
            "success": True,
            "status": "SENT",
            "draft_id": str(draft.id),
            "attempt_id": str(attempt.id),
        }

    else:
        # Failure or Blocked
        if command_result.status == CommandExecutionStatus.BLOCKED:
            draft.status = DraftStatus.REJECTED.value
            await db.commit()

        return {
            "success": False,
            "status": command_result.status.value,
            "draft_id": str(draft.id),
            "error": command_result.error or "Browser execution failed",
        }


# --- WebSocket Endpoint ---

@router.websocket("/ws")
async def browser_websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
):
    """
    Real-time bidirectional WebSocket between Chrome extension and FastAPI.
    Authenticates short-lived session token, routes commands, receives DOM states and results.
    """
    await websocket.accept()

    # Authenticate token
    if not token:
        await websocket.close(code=4001, reason="Missing session token")
        return

    session_record = browser_gateway.validate_session_token(token)
    if not session_record:
        await websocket.close(code=4003, reason="Invalid or expired session token")
        return

    session_id = session_record["session_id"]
    org_id = session_record["organization_id"]
    user_id = session_record.get("user_id")

    await browser_gateway.register_connection(
        session_id=session_id,
        websocket=websocket,
        org_id=org_id,
        user_id=user_id,
    )

    try:
        # Send initial ACK frame
        await websocket.send_json({
            "frame_type": "CONNECTED_ACK",
            "payload": {
                "session_id": str(session_id),
                "organization_id": str(org_id),
                "status": "CONNECTED",
            },
        })

        while True:
            data = await websocket.receive_json()
            await browser_gateway.handle_incoming_frame(session_id=session_id, frame=data)

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected cleanly: session_id={session_id}")
    except Exception as e:
        logger.warning(f"WebSocket error for session_id={session_id}: {e}")
    finally:
        await browser_gateway.unregister_connection(session_id)
