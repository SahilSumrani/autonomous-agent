import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from packages.shared_types.outreach import (
    CtaCategory,
    DraftStatus,
    OutreachAngle,
    OutreachChannel,
    PainPointCategory,
    PersonalizationLevel,
)


class OutreachEvidenceModel(BaseModel):
    """Verifiable claim supporting generated outreach draft."""
    claim: str
    source_url: Optional[str] = None
    evidence_text: str
    evidence_type: str = "BROWSER_OBSERVATION"
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)


class PainPoint(BaseModel):
    """Structured prospect pain point backed by evidence."""
    category: PainPointCategory
    statement: str
    evidence: str
    source_url: Optional[str] = None
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    severity: str = "MEDIUM"  # LOW, MEDIUM, HIGH


class OutreachContext(BaseModel):
    """Unified context aggregated across CRM, Phase 3 signals, and Phase 4 audits."""
    lead_id: uuid.UUID
    company_name: Optional[str] = None
    company_id: Optional[uuid.UUID] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_handle: Optional[str] = None
    source: str
    source_url: Optional[str] = None

    business_summary: Optional[str] = None
    verified_observations: List[str] = Field(default_factory=list)
    verified_signals: List[str] = Field(default_factory=list)

    lead_score: int = 50
    lead_category: str = "MEDIUM"

    recommended_service: str = "BUSINESS_WEBSITE"
    alternative_services: List[str] = Field(default_factory=list)

    website_url: Optional[str] = None
    website_findings: Dict[str, Any] = Field(default_factory=dict)
    website_opportunities: Dict[str, Any] = Field(default_factory=dict)

    pain_points: List[PainPoint] = Field(default_factory=list)
    opportunity_points: List[str] = Field(default_factory=list)

    decision_maker: Optional[str] = None
    decision_maker_confidence: float = 0.0

    recent_activity: Optional[str] = None
    previous_outreach: List[Dict[str, Any]] = Field(default_factory=list)
    previous_replies: List[Dict[str, Any]] = Field(default_factory=list)

    recommended_channel: OutreachChannel = OutreachChannel.INSTAGRAM_DM
    recommended_angle: OutreachAngle = OutreachAngle.WEBSITE_IMPROVEMENT

    evidence: List[OutreachEvidenceModel] = Field(default_factory=list)
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)


class MessageValidationResult(BaseModel):
    """Deterministic validation and quality score result."""
    valid: bool
    score: int = Field(ge=0, le=100)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    unsupported_claims: List[str] = Field(default_factory=list)
    evidence_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    personalization_score: int = Field(default=0, ge=0, le=100)


class OutreachDraftResult(BaseModel):
    """Generated draft output ready for validation or approval."""
    variant: str = "A"
    channel: OutreachChannel
    subject: Optional[str] = None
    body: str
    personalization_level: PersonalizationLevel
    angle: OutreachAngle
    service: str
    cta_text: Optional[str] = None
    cta_category: Optional[CtaCategory] = None
    quality_score: int = 0
    validation_result: Optional[MessageValidationResult] = None
    evidence_items: List[OutreachEvidenceModel] = Field(default_factory=list)
    status: DraftStatus = DraftStatus.DRAFT
    suggested_follow_up_days: Optional[int] = 3
