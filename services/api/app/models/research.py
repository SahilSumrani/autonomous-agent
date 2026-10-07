import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.api.app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WebsiteResearch(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Deep website intelligence and technical audit findings for a lead."""
    __tablename__ = "website_research"

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
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    website_url: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="PENDING", nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    pages_analyzed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pages_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Technology Stack
    technology_stack: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    cms: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    frontend_framework: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    backend_technology: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    analytics_tools: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    payment_provider: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    hosting_provider: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    cdn: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    ecommerce_platform: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # Audited Scores (0-100)
    website_health_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    performance_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mobile_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ux_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    seo_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    conversion_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    accessibility_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Website Opportunity Score (0-100)
    opportunity_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    # Findings & Summaries
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    positive_findings: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    negative_findings: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    recommendations: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)

    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Relationships
    lead: Mapped["Lead"] = relationship("Lead", foreign_keys=[lead_id])
    pages: Mapped[List["WebsitePageResearch"]] = relationship(
        "WebsitePageResearch",
        back_populates="research",
        cascade="all, delete-orphan",
        order_by="WebsitePageResearch.created_at",
    )


class WebsitePageResearch(Base, UUIDPrimaryKeyMixin):
    """Specific page findings and observations within a website research audit."""
    __tablename__ = "website_page_research"

    research_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("website_research.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    page_type: Mapped[str] = mapped_column(String(64), default="OTHER", nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    content_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    visible_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    links_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Feature Flags
    has_cta: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_contact_form: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_phone: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_email: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_pricing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_product_catalog: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_checkout: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_social_proof: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_testimonials: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_reviews: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Category Observations
    mobile_observations: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    ux_observations: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    seo_observations: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    performance_observations: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    conversion_observations: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    research: Mapped["WebsiteResearch"] = relationship("WebsiteResearch", back_populates="pages")
