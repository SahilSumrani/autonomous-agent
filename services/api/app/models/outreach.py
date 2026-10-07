import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.shared_types.outreach import (
    DraftStatus,
    OutreachChannel,
    PersonalizationLevel,
)
from services.api.app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class OutreachCampaign(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Container for organizing outreach efforts across channels."""
    __tablename__ = "outreach_campaigns"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    channel: Mapped[str] = mapped_column(String(50), nullable=False, default=OutreachChannel.INSTAGRAM_DM.value)
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE", nullable=False)

    # Relationships
    drafts: Mapped[List["OutreachDraft"]] = relationship(
        "OutreachDraft",
        back_populates="campaign",
        cascade="all, delete-orphan",
    )


class OutreachDraft(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Evidence-backed personalized outreach message draft."""
    __tablename__ = "outreach_drafts"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    campaign_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("outreach_campaigns.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    channel: Mapped[str] = mapped_column(
        String(50),
        default=OutreachChannel.INSTAGRAM_DM.value,
        nullable=False,
        index=True,
    )
    variant: Mapped[str] = mapped_column(String(10), default="A", nullable=False)
    subject: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    personalization_level: Mapped[str] = mapped_column(
        String(50),
        default=PersonalizationLevel.DEEP.value,
        nullable=False,
    )
    angle: Mapped[str] = mapped_column(String(100), nullable=False)
    recommended_service: Mapped[str] = mapped_column(String(100), nullable=False)
    quality_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        default=DraftStatus.DRAFT.value,
        nullable=False,
        index=True,
    )
    cta_text: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    cta_category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    suggested_follow_up_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    follow_up_reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Relationships
    campaign: Mapped[Optional["OutreachCampaign"]] = relationship("OutreachCampaign", back_populates="drafts")
    evidences: Mapped[List["OutreachEvidence"]] = relationship(
        "OutreachEvidence",
        back_populates="draft",
        cascade="all, delete-orphan",
    )
    approvals: Mapped[List["OutreachApproval"]] = relationship(
        "OutreachApproval",
        back_populates="draft",
        cascade="all, delete-orphan",
    )
    attempts: Mapped[List["OutreachAttempt"]] = relationship(
        "OutreachAttempt",
        back_populates="draft",
    )

    __table_args__ = (
        Index("ix_outreach_drafts_org_lead", "organization_id", "lead_id"),
        Index("ix_outreach_drafts_org_status", "organization_id", "status"),
    )


class OutreachEvidence(Base, UUIDPrimaryKeyMixin):
    """Specific verifiable claim supporting an outreach draft."""
    __tablename__ = "outreach_evidences"

    draft_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("outreach_drafts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    claim: Mapped[str] = mapped_column(String(512), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.9, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    draft: Mapped["OutreachDraft"] = relationship("OutreachDraft", back_populates="evidences")


class OutreachApproval(Base, UUIDPrimaryKeyMixin):
    """Human approval gate record for outreach drafts."""
    __tablename__ = "outreach_approvals"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    draft_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("outreach_drafts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    requested_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False, index=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    draft: Mapped["OutreachDraft"] = relationship("OutreachDraft", back_populates="approvals")


class OutreachAttempt(Base, UUIDPrimaryKeyMixin):
    """Audit log of outreach generation attempts and duplicate checks."""
    __tablename__ = "outreach_attempts"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    draft_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("outreach_drafts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    channel: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    recipient: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="RECORDED", nullable=False, index=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    draft: Mapped[Optional["OutreachDraft"]] = relationship("OutreachDraft", back_populates="attempts")
