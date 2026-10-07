import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from packages.shared_types.agent import (
    ActionType,
    AgentState,
    ApprovalStatus,
    SessionStatus,
    ToolPermissionLevel,
    ToolRiskLevel,
)


class SessionStartRequest(BaseModel):
    browser_id: str = Field(..., min_length=1, max_length=255)
    initial_url: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None


class SessionStateUpdateRequest(BaseModel):
    target_state: AgentState
    reason: Optional[str] = None


class SessionResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    browser_id: str
    current_url: Optional[str] = None
    current_domain: Optional[str] = None
    status: str
    started_at: datetime
    last_activity_at: datetime
    ended_at: Optional[datetime] = None
    metadata_json: Optional[Dict[str, Any]] = None
    model_config = ConfigDict(from_attributes=True)


class AgentEventCreate(BaseModel):
    event_type: str = Field(..., min_length=1, max_length=100)
    tool: Optional[str] = None
    url: Optional[str] = None
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    status: str = "SUCCESS"
    duration_ms: Optional[float] = None
    metadata_json: Optional[Dict[str, Any]] = None


class AgentEventResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    event_type: str
    tool: Optional[str] = None
    url: Optional[str] = None
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    status: str
    duration_ms: Optional[float] = None
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PageObservationRequest(BaseModel):
    url: str = Field(..., min_length=1)
    visible_text: str = Field(..., min_length=1)
    recipient_handle: Optional[str] = None
    profile_url: Optional[str] = None


class PageObservationResponse(BaseModel):
    is_opportunity: bool
    opportunity_type: Optional[str] = None
    confidence: Optional[float] = None
    lead_id: Optional[str] = None
    approval_id: Optional[str] = None
    draft_content: Optional[str] = None
    approval_status: Optional[str] = None
    message: Optional[str] = None
    overall_score: Optional[int] = None
    category: Optional[str] = None
    score_breakdown: Optional[Dict[str, Any]] = None
    recommended_service: Optional[str] = None
    recommended_next_action: Optional[str] = None


class ActionApprovalResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    lead_id: Optional[uuid.UUID] = None
    action_type: str
    target_url: Optional[str] = None
    recipient: Optional[str] = None
    content: str
    status: str
    requested_at: datetime
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None
    model_config = ConfigDict(from_attributes=True)


class ApprovalDecisionRequest(BaseModel):
    decision: str = Field(..., description="'APPROVED' or 'REJECTED'")
    reviewer: str = Field(default="Sahil")
