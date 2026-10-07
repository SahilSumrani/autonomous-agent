import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
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
from services.api.app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ConversationThread(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Represents a multi-turn conversation thread with a prospect across channels."""
    __tablename__ = "conversation_threads"

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
    channel: Mapped[str] = mapped_column(String(50), nullable=False, default="INSTAGRAM_DM")
    external_thread_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=ThreadStatus.ACTIVE.value, index=True)
    current_intent: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sentiment: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sales_stage: Mapped[str] = mapped_column(String(50), nullable=False, default=SalesStage.CONTACTED.value, index=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Relationships
    messages: Mapped[List["ConversationMessage"]] = relationship(
        "ConversationMessage",
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.created_at.asc()",
        lazy="selectin",
    )
    replies: Mapped[List["ConversationReplyDraft"]] = relationship(
        "ConversationReplyDraft",
        back_populates="thread",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    approvals: Mapped[List["ConversationApproval"]] = relationship(
        "ConversationApproval",
        back_populates="thread",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_conversation_threads_org_lead", "organization_id", "lead_id"),
        Index("ix_conversation_threads_org_status", "organization_id", "status"),
    )


class ConversationMessage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Individual message within a conversation thread."""
    __tablename__ = "conversation_messages"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    thread_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("conversation_threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    direction: Mapped[str] = mapped_column(String(20), nullable=False, default=MessageDirection.INBOUND.value)
    author_type: Mapped[str] = mapped_column(String(20), nullable=False, default=MessageAuthorType.PROSPECT.value)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sanitized_content: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    external_message_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    delivery_status: Mapped[str] = mapped_column(String(50), nullable=False, default=MessageDeliveryStatus.RECEIVED.value)
    evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Relationships
    thread: Mapped["ConversationThread"] = relationship("ConversationThread", back_populates="messages")

    __table_args__ = (
        Index("ix_conversation_messages_org_thread", "organization_id", "thread_id"),
        Index("ix_conversation_messages_ext_ref", "external_message_ref"),
    )


class ConversationReplyDraft(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Generated reply draft for an inbound prospect message."""
    __tablename__ = "conversation_reply_drafts"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    thread_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("conversation_threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    in_reply_to_message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("conversation_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    variant: Mapped[str] = mapped_column(String(20), nullable=False, default="DIRECT")
    objective: Mapped[str] = mapped_column(String(50), nullable=False, default=ReplyObjective.ANSWER.value)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    quality_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT")
    evidence_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_flags: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    requires_human_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Relationships
    thread: Mapped["ConversationThread"] = relationship("ConversationThread", back_populates="replies")
    approvals: Mapped[List["ConversationApproval"]] = relationship(
        "ConversationApproval",
        back_populates="reply",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_conversation_reply_drafts_org_thread", "organization_id", "thread_id"),
        Index("ix_conversation_reply_drafts_status", "status"),
    )


class ConversationApproval(Base, UUIDPrimaryKeyMixin):
    """Explicit human approval record for sending a conversation reply."""
    __tablename__ = "conversation_approvals"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    thread_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("conversation_threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reply_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("conversation_reply_drafts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=ReplyApprovalStatus.PENDING.value)
    reviewer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    thread: Mapped["ConversationThread"] = relationship("ConversationThread", back_populates="approvals")
    reply: Mapped["ConversationReplyDraft"] = relationship("ConversationReplyDraft", back_populates="approvals")

    __table_args__ = (
        Index("ix_conversation_approvals_org_thread", "organization_id", "thread_id"),
        Index("ix_conversation_approvals_status", "status"),
    )
