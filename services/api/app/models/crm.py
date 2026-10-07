import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.shared_types.crm import (
    ActorType,
    CompanyStatus,
    LeadStatus,
    LeadType,
    SignalType,
    SourceType,
    UserRole,
)
from services.api.app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Organization(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Multi-tenant organization/workspace entity."""
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    # Relationships
    users: Mapped[List["User"]] = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    companies: Mapped[List["Company"]] = relationship("Company", back_populates="organization", cascade="all, delete-orphan")
    contacts: Mapped[List["Contact"]] = relationship("Contact", back_populates="organization", cascade="all, delete-orphan")
    leads: Mapped[List["Lead"]] = relationship("Lead", back_populates="organization", cascade="all, delete-orphan")
    lead_sources: Mapped[List["LeadSource"]] = relationship("LeadSource", back_populates="organization", cascade="all, delete-orphan")


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """User account belonging to an organization."""
    __tablename__ = "users"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default=UserRole.MEMBER.value, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="users")

    __table_args__ = (
        UniqueConstraint("organization_id", "email", name="uq_user_org_email"),
    )


class Company(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Target or discovered business entity."""
    __tablename__ = "companies"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    normalized_domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    website_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    instagram_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    reddit_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default=CompanyStatus.UNKNOWN.value, nullable=False)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="companies")
    contacts: Mapped[List["Contact"]] = relationship("Contact", back_populates="company")
    leads: Mapped[List["Lead"]] = relationship("Lead", back_populates="company")

    __table_args__ = (
        Index("ix_companies_org_domain", "organization_id", "normalized_domain"),
        Index("ix_companies_org_name", "organization_id", "normalized_name"),
    )


class Contact(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Person/Prospect associated with a company or lead."""
    __tablename__ = "contacts"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    job_title: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    instagram_username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    instagram_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    reddit_username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    reddit_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True, index=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="contacts")
    company: Mapped[Optional["Company"]] = relationship("Company", back_populates="contacts")
    leads: Mapped[List["Lead"]] = relationship("Lead", back_populates="contact")

    __table_args__ = (
        Index("ix_contacts_org_email", "organization_id", "email"),
    )


class LeadSource(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Reusable source/channel definition for tracking client acquisition origins."""
    __tablename__ = "lead_sources"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(50), default=SourceType.WEB.value, nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="lead_sources")
    leads: Mapped[List["Lead"]] = relationship("Lead", back_populates="source")


class Lead(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Central client acquisition sales opportunity."""
    __tablename__ = "leads"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    contact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("contacts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("lead_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(String(50), default=LeadStatus.NEW.value, nullable=False, index=True)
    lead_type: Mapped[str] = mapped_column(String(50), default=LeadType.COMPANY.value, nullable=False, index=True)

    source_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    profile_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True, index=True)
    content_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    intent_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    qualification_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    overall_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)

    recommended_service: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    organization: Mapped["Organization"] = relationship("Organization", back_populates="leads")
    company: Mapped[Optional["Company"]] = relationship("Company", back_populates="leads")
    contact: Mapped[Optional["Contact"]] = relationship("Contact", back_populates="leads")
    source: Mapped[Optional["LeadSource"]] = relationship("LeadSource", back_populates="leads")

    signals: Mapped[List["LeadSignal"]] = relationship("LeadSignal", back_populates="lead", cascade="all, delete-orphan")
    pipeline_events: Mapped[List["PipelineEvent"]] = relationship("PipelineEvent", back_populates="lead", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("intent_score >= 0 AND intent_score <= 100", name="chk_lead_intent_score"),
        CheckConstraint("qualification_score >= 0 AND qualification_score <= 100", name="chk_lead_qualification_score"),
        CheckConstraint("overall_score >= 0 AND overall_score <= 100", name="chk_lead_overall_score"),
        Index("ix_leads_org_status", "organization_id", "status"),
        Index("ix_leads_org_score", "organization_id", "overall_score"),
        Index("ix_leads_org_profile", "organization_id", "profile_url"),
    )


class LeadSignal(Base, UUIDPrimaryKeyMixin):
    """Detected buying or need signal associated with a lead."""
    __tablename__ = "lead_signals"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    signal_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    lead: Mapped["Lead"] = relationship("Lead", back_populates="signals")

    __table_args__ = (
        CheckConstraint("confidence >= 0.0 AND confidence <= 1.0", name="chk_signal_confidence"),
    )


class PipelineEvent(Base, UUIDPrimaryKeyMixin):
    """Immutable audit trail of lead status transitions."""
    __tablename__ = "pipeline_events"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    old_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    actor_type: Mapped[str] = mapped_column(String(50), default=ActorType.SYSTEM.value, nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    lead: Mapped["Lead"] = relationship("Lead", back_populates="pipeline_events")
