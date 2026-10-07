import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from packages.shared_types.conversation import (
    MessageAuthorType,
    MessageDeliveryStatus,
    MessageDirection,
    ProspectIntent,
    ReplyApprovalStatus,
    ReplyObjective,
    SalesStage,
    ThreadStatus,
)


class ConversationThreadCreate(BaseModel):
    lead_id: Optional[uuid.UUID] = None
    channel: str = "INSTAGRAM_DM"
    external_thread_ref: Optional[str] = None
    initial_message: Optional[str] = None


class ConversationMessageResponse(BaseModel):
    id: uuid.UUID
    thread_id: uuid.UUID
    direction: str
    author_type: str
    content: str
    sanitized_content: str
    source_url: Optional[str] = None
    external_message_ref: Optional[str] = None
    delivery_status: str
    evidence: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationThreadResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    lead_id: uuid.UUID
    channel: str
    external_thread_ref: Optional[str] = None
    status: str
    current_intent: Optional[str] = None
    sentiment: Optional[str] = None
    sales_stage: str
    summary: Optional[str] = None
    last_message_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    messages: Optional[List[ConversationMessageResponse]] = None

    model_config = ConfigDict(from_attributes=True)


class ConversationMessageIngestRequest(BaseModel):
    content: str = Field(..., min_length=1, description="Raw message text from prospect")
    external_message_ref: Optional[str] = None
    source_url: Optional[str] = None
    author_type: str = MessageAuthorType.PROSPECT.value
    direction: str = MessageDirection.INBOUND.value


class ConversationReplyDraftResponse(BaseModel):
    id: uuid.UUID
    thread_id: uuid.UUID
    in_reply_to_message_id: Optional[uuid.UUID] = None
    variant: str
    objective: str
    body: str
    quality_score: int
    confidence: float
    status: str
    evidence_text: Optional[str] = None
    risk_flags: Optional[List[str]] = None
    requires_human_approval: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationApprovalResponse(BaseModel):
    id: uuid.UUID
    thread_id: uuid.UUID
    reply_id: uuid.UUID
    status: str
    reviewer_id: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    decision_reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


ConversationReplyApprovalResponse = ConversationApprovalResponse


class ConversationReplyGenerateRequest(BaseModel):
    in_reply_to_message_id: Optional[uuid.UUID] = None
    specific_instructions: Optional[str] = None


class ConversationReplyApproveRequest(BaseModel):
    reviewer_id: str = "Sahil"
    decision_reason: Optional[str] = None


class ConversationReplyRejectRequest(BaseModel):
    reviewer_id: str = "Sahil"
    rejection_reason: str = Field(..., min_length=1)


class ConversationSendRequest(BaseModel):
    session_id: uuid.UUID = Field(..., description="Active Phase 6 Chrome browser session ID")


class ConversationSendResponse(BaseModel):
    success: bool
    status: str  # SENT, DELIVERY_UNKNOWN, FAILED, BLOCKED
    reply_id: uuid.UUID
    thread_id: uuid.UUID
    detail: str


class ConversationAnalysisResponse(BaseModel):
    thread_id: uuid.UUID
    intent: str
    confidence: float
    evidence: str
    objection_detected: Optional[str] = None
    sales_stage: str
    recommended_objective: str
    rolling_summary: str
