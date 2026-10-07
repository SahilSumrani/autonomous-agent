import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from packages.shared_types.outreach import (
    CtaCategory,
    DraftStatus,
    OutreachAngle,
    OutreachChannel,
    PersonalizationLevel,
)


class GenerateOutreachRequest(BaseModel):
    channel: Optional[OutreachChannel] = None
    variant_count: int = Field(default=3, ge=1, le=3)
    preferences: Optional[List[str]] = None  # e.g. ["shorter", "more conversational"]
    override_duplicate: bool = False


class RegenerateOutreachRequest(BaseModel):
    preferences: Optional[List[str]] = Field(default=None)  # e.g. ["shorter", "insight-led", "more direct"]
    target_channel: Optional[OutreachChannel] = None


class ApproveDraftRequest(BaseModel):
    reviewed_by: Optional[str] = "SAHIL"
    decision_reason: Optional[str] = "Verified high-quality personalized outreach draft."


class RejectDraftRequest(BaseModel):
    reviewed_by: Optional[str] = "SAHIL"
    decision_reason: str = Field(..., min_length=3)


class OutreachEvidenceResponse(BaseModel):
    id: uuid.UUID
    draft_id: uuid.UUID
    claim: str
    source_url: Optional[str] = None
    evidence_text: str
    evidence_type: str
    confidence: float
    created_at: datetime


class OutreachApprovalResponse(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    draft_id: uuid.UUID
    channel: str
    requested_by: Optional[str] = None
    status: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    decision_reason: Optional[str] = None
    created_at: datetime


class OutreachAttemptResponse(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    draft_id: Optional[uuid.UUID] = None
    channel: str
    recipient: Optional[str] = None
    status: str
    reason: Optional[str] = None
    created_at: datetime


class OutreachDraftResponse(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    campaign_id: Optional[uuid.UUID] = None
    channel: OutreachChannel
    variant: str
    subject: Optional[str] = None
    body: str
    personalization_level: PersonalizationLevel
    angle: OutreachAngle
    recommended_service: str
    quality_score: int
    confidence: float
    status: DraftStatus
    cta_text: Optional[str] = None
    cta_category: Optional[str] = None
    suggested_follow_up_at: Optional[datetime] = None
    follow_up_reason: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    evidences: List[OutreachEvidenceResponse] = Field(default_factory=list)


class OutreachHistoryResponse(BaseModel):
    lead_id: uuid.UUID
    drafts: List[OutreachDraftResponse] = Field(default_factory=list)
    approvals: List[OutreachApprovalResponse] = Field(default_factory=list)
    attempts: List[OutreachAttemptResponse] = Field(default_factory=list)


class ValidationDetailResponse(BaseModel):
    valid: bool
    score: int
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    unsupported_claims: List[str] = Field(default_factory=list)
    evidence_coverage: float
    personalization_score: int
