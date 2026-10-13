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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.shared_types.prospecting import (
    CandidateStatus,
    ProspectingJobEndReason,
    ProspectingJobStatus,
    ProspectingSourceType,
)
from services.api.app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProspectingJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """First-class autonomous prospecting job with bounded execution limits."""
    __tablename__ = "prospecting_jobs"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agent_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default=ProspectingJobStatus.CREATED.value,
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(
        String(50),
        default=ProspectingSourceType.WEBSITE.value,
        nullable=False,
        index=True,
    )
    query: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    target_service: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    target_industries: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    target_geography: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Budgets
    max_candidates: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    max_pages: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    max_scrolls: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    max_time_seconds: Mapped[int] = mapped_column(Integer, default=1800, nullable=False)

    # Timing
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    end_reason: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    statistics: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=lambda: {
            "candidates_found": 0,
            "candidates_qualified": 0,
            "candidates_disqualified": 0,
            "pages_visited": 0,
            "scrolls_performed": 0,
            "leads_created": 0,
            "outreach_drafted": 0,
        },
        nullable=False,
    )
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Relationships
    candidates: Mapped[List["ProspectCandidate"]] = relationship(
        "ProspectCandidate",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="ProspectCandidate.first_seen",
    )
    observations: Mapped[List["ProspectObservation"]] = relationship(
        "ProspectObservation",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="ProspectObservation.created_at",
    )

    __table_args__ = (
        Index("ix_prospecting_jobs_org_status", "organization_id", "status"),
    )


class ProspectCandidate(Base, UUIDPrimaryKeyMixin):
    """Normalized prospect candidate identified during prospecting."""
    __tablename__ = "prospect_candidates"

    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("prospecting_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    canonical_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    username_or_handle: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    business_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    discovery_evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        default=CandidateStatus.DISCOVERED.value,
        nullable=False,
        index=True,
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    dedup_key: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    linked_lead_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("leads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    job: Mapped["ProspectingJob"] = relationship("ProspectingJob", back_populates="candidates")
    observations: Mapped[List["ProspectObservation"]] = relationship(
        "ProspectObservation",
        back_populates="candidate",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_prospect_candidates_job_status", "job_id", "status"),
        UniqueConstraint("job_id", "dedup_key", name="uq_prospect_candidates_job_dedup"),
    )


class ProspectObservation(Base, UUIDPrimaryKeyMixin):
    """Durable representation of content observations made during prospecting."""
    __tablename__ = "prospect_observations"

    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("prospecting_jobs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    candidate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("prospect_candidates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agent_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    page_title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    visible_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    headings: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    links: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    job: Mapped[Optional["ProspectingJob"]] = relationship("ProspectingJob", back_populates="observations")
    candidate: Mapped[Optional["ProspectCandidate"]] = relationship("ProspectCandidate", back_populates="observations")


class ProspectingProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Organization-scoped autonomous prospecting profile."""
    __tablename__ = "prospecting_profiles"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    services_offered: Mapped[List[str]] = mapped_column(
        JSON,
        default=lambda: ["AI automation", "Web Development", "Mobile Apps", "Custom Software"],
        nullable=False,
    )
    ideal_customer_keywords: Mapped[List[str]] = mapped_column(
        JSON,
        default=lambda: [
            "need a website",
            "looking for developer",
            "build MVP",
            "automation workflow",
            "website redesign",
            "hire developer",
        ],
        nullable=False,
    )
    excluded_keywords: Mapped[List[str]] = mapped_column(
        JSON,
        default=lambda: [
            "student",
            "homework",
            "free",
            "internship",
            "hiring employee",
            "full-time job",
        ],
        nullable=False,
    )
    sources_enabled: Mapped[List[str]] = mapped_column(
        JSON,
        default=lambda: ["REDDIT", "THREADS", "WEBSITE"],
        nullable=False,
    )
    daily_limits_json: Mapped[Dict[str, int]] = mapped_column(
        JSON,
        default=lambda: {"REDDIT": 25, "THREADS": 25, "WEBSITE": 50, "LINKEDIN": 10},
        nullable=False,
    )
    geography: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default="Global")

