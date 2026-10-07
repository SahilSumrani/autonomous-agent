import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.shared_types.agent import (
    ActionType,
    ApprovalStatus,
    SessionStatus,
)
from services.api.app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AgentSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """User-authorized browser research agent session."""
    __tablename__ = "agent_sessions"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    browser_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    current_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    current_domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[str] = mapped_column(
        String(50),
        default=SessionStatus.IDLE.value,
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Relationships
    events: Mapped[List["AgentEvent"]] = relationship(
        "AgentEvent",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="AgentEvent.created_at",
    )
    approvals: Mapped[List["ActionApproval"]] = relationship(
        "ActionApproval",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ActionApproval.requested_at",
    )

    __table_args__ = (
        Index("ix_agent_sessions_org_status", "organization_id", "status"),
    )


class AgentEvent(Base, UUIDPrimaryKeyMixin):
    """Auditable log of actions and observations within an agent session."""
    __tablename__ = "agent_events"

    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agent_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    tool: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    input_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="SUCCESS", nullable=False)
    duration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    session: Mapped["AgentSession"] = relationship("AgentSession", back_populates="events")


class ActionApproval(Base, UUIDPrimaryKeyMixin):
    """Human-in-the-loop safety gate for outbound comments, DMs, and high-risk actions."""
    __tablename__ = "action_approvals"

    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agent_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("leads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action_type: Mapped[str] = mapped_column(
        String(50),
        default=ActionType.DM.value,
        nullable=False,
        index=True,
    )
    target_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    recipient: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        default=ApprovalStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    session: Mapped["AgentSession"] = relationship("AgentSession", back_populates="approvals")
