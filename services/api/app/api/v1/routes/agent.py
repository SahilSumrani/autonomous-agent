import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.agent_core.tools import BrowserToolRegistry
from packages.shared_types.agent import ApprovalStatus
from services.api.app.api.v1.dependencies.auth import get_current_org_id
from services.api.app.core.database import get_db
from services.api.app.models.agent import ActionApproval, AgentEvent
from services.api.app.schemas.agent import (
    ActionApprovalResponse,
    AgentEventCreate,
    AgentEventResponse,
    ApprovalDecisionRequest,
    PageObservationRequest,
    PageObservationResponse,
    SessionResponse,
    SessionStartRequest,
    SessionStateUpdateRequest,
)
from services.api.app.services.agent_service import (
    ActionBlockedException,
    AgentService,
    AgentServiceException,
)

router = APIRouter(prefix="/agent", tags=["Browser Agent"])


@router.get("/tools")
async def list_tools() -> Dict[str, Any]:
    """List available browser tools, their risk boundaries, and approval requirements."""
    tools = BrowserToolRegistry.list_tools()
    return {name: tool.model_dump() for name, tool in tools.items()}


@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def start_session(
    data: SessionStartRequest,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> SessionResponse:
    service = AgentService(db)
    agent_session = await service.create_session(
        org_id=org_id,
        browser_id=data.browser_id,
        initial_url=data.initial_url,
        metadata=data.metadata_json,
    )
    return SessionResponse.model_validate(agent_session)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> SessionResponse:
    service = AgentService(db)
    try:
        agent_session = await service.get_session(org_id, session_id)
        return SessionResponse.model_validate(agent_session)
    except AgentServiceException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/sessions/{session_id}/state", response_model=SessionResponse)
async def update_session_state(
    session_id: uuid.UUID,
    data: SessionStateUpdateRequest,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> SessionResponse:
    service = AgentService(db)
    try:
        agent_session = await service.update_session_state(
            org_id=org_id,
            session_id=session_id,
            target_state=data.target_state,
            reason=data.reason,
        )
        return SessionResponse.model_validate(agent_session)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))


@router.post("/sessions/{session_id}/events", response_model=AgentEventResponse, status_code=status.HTTP_201_CREATED)
async def record_event(
    session_id: uuid.UUID,
    data: AgentEventCreate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> AgentEventResponse:
    service = AgentService(db)
    try:
        event = await service.record_event(
            org_id=org_id,
            session_id=session_id,
            event_type=data.event_type,
            tool=data.tool,
            url=data.url,
            input_summary=data.input_summary,
            output_summary=data.output_summary,
            status=data.status,
            duration_ms=data.duration_ms,
            metadata=data.metadata_json,
        )
        return AgentEventResponse.model_validate(event)
    except AgentServiceException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/sessions/{session_id}/events", response_model=List[AgentEventResponse])
async def list_events(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> List[AgentEventResponse]:
    service = AgentService(db)
    await service.get_session(org_id, session_id)  # Validate org ownership
    stmt = (
        select(AgentEvent)
        .where(AgentEvent.session_id == session_id)
        .order_by(desc(AgentEvent.created_at))
    )
    res = await db.execute(stmt)
    events = res.scalars().all()
    return [AgentEventResponse.model_validate(e) for e in events]


@router.post("/sessions/{session_id}/observe", response_model=PageObservationResponse)
async def observe_page(
    session_id: uuid.UUID,
    data: PageObservationRequest,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> PageObservationResponse:
    service = AgentService(db)
    try:
        result = await service.observe_and_process_page(
            org_id=org_id,
            session_id=session_id,
            url=data.url,
            visible_text=data.visible_text,
            recipient_handle=data.recipient_handle,
            profile_url=data.profile_url,
        )
        return PageObservationResponse(**result)
    except ActionBlockedException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except AgentServiceException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/approvals", response_model=List[ActionApprovalResponse])
async def list_approvals(
    status_filter: Optional[ApprovalStatus] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> List[ActionApprovalResponse]:
    from services.api.app.models.agent import AgentSession
    query = (
        select(ActionApproval)
        .join(AgentSession, ActionApproval.session_id == AgentSession.id)
        .where(AgentSession.organization_id == org_id)
    )
    if status_filter:
        query = query.where(ActionApproval.status == status_filter.value)
    query = query.order_by(desc(ActionApproval.requested_at))

    res = await db.execute(query)
    items = res.scalars().all()
    return [ActionApprovalResponse.model_validate(item) for item in items]


@router.post("/approvals/{approval_id}/review", response_model=ActionApprovalResponse)
async def review_approval(
    approval_id: uuid.UUID,
    data: ApprovalDecisionRequest,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> ActionApprovalResponse:
    service = AgentService(db)
    try:
        approval = await service.review_action_approval(
            org_id=org_id,
            approval_id=approval_id,
            decision=data.decision,
            reviewer=data.reviewer,
        )
        return ActionApprovalResponse.model_validate(approval)
    except AgentServiceException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/approvals/{approval_id}/execute", response_model=ActionApprovalResponse)
async def execute_action(
    approval_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> ActionApprovalResponse:
    service = AgentService(db)
    try:
        approval = await service.execute_approved_action(
            org_id=org_id,
            approval_id=approval_id,
        )
        return ActionApprovalResponse.model_validate(approval)
    except ActionBlockedException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except AgentServiceException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
