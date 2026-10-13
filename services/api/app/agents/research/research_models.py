import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EvidenceCategory(str, Enum):
    TECHNOLOGY = "TECHNOLOGY"
    PERFORMANCE = "PERFORMANCE"
    MOBILE = "MOBILE"
    UX = "UX"
    SEO = "SEO"
    CONVERSION = "CONVERSION"
    ECOMMERCE = "ECOMMERCE"
    BUSINESS = "BUSINESS"
    CONTENT = "CONTENT"
    ACCESSIBILITY = "ACCESSIBILITY"


class ResearchDataSource(str, Enum):
    OBSERVED_DATA = "OBSERVED_DATA"
    USER_SUPPLIED_DATA = "USER_SUPPLIED_DATA"
    UNAVAILABLE_DATA = "UNAVAILABLE_DATA"


class ResearchStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    RESEARCH_UNAVAILABLE = "RESEARCH_UNAVAILABLE"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class PageType(str, Enum):
    HOMEPAGE = "HOMEPAGE"
    ABOUT = "ABOUT"
    SERVICES = "SERVICES"
    PRODUCTS = "PRODUCTS"
    PRICING = "PRICING"
    SHOP = "SHOP"
    STORE = "STORE"
    CONTACT = "CONTACT"
    PORTFOLIO = "PORTFOLIO"
    CASE_STUDIES = "CASE_STUDIES"
    BLOG = "BLOG"
    OTHER = "OTHER"


class ResearchEvidence(BaseModel):
    """Observable verifiable evidence item extracted from research."""
    category: str
    statement: str
    source_url: str
    source_type: str = "PAGE_OBSERVATION"
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)


class TechnologyFinding(BaseModel):
    """Specific technology or platform detected from observable indicators."""
    technology: str
    category: str  # FRONTEND, BACKEND, ECOMMERCE, ANALYTICS, CDN_INFRASTRUCTURE, CMS
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    evidence: str


class WebsiteResolution(BaseModel):
    """Result of resolving a lead's primary public website."""
    found: bool
    primary_url: Optional[str] = None
    alternatives: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: List[ResearchEvidence] = Field(default_factory=list)


class PageAnalysisResult(BaseModel):
    """Structured extraction and audit result for a single inspected page."""
    url: str
    page_type: str = PageType.OTHER.value
    title: Optional[str] = None
    status_code: Optional[int] = 200
    content_summary: Optional[str] = None
    visible_text: Optional[str] = None
    links_count: int = 0

    has_cta: bool = False
    has_contact_form: bool = False
    has_phone: bool = False
    has_email: bool = False
    has_pricing: bool = False
    has_product_catalog: bool = False
    has_checkout: bool = False
    has_social_proof: bool = False
    has_testimonials: bool = False
    has_reviews: bool = False

    mobile_observations: List[str] = Field(default_factory=list)
    ux_observations: List[str] = Field(default_factory=list)
    seo_observations: List[str] = Field(default_factory=list)
    performance_observations: List[str] = Field(default_factory=list)
    conversion_observations: List[str] = Field(default_factory=list)
    evidence: List[ResearchEvidence] = Field(default_factory=list)


class AuditScores(BaseModel):
    """Evaluated technical scores across all audited pages (0-100)."""
    website_health_score: int = Field(default=70, ge=0, le=100)
    performance_score: int = Field(default=70, ge=0, le=100)
    mobile_score: int = Field(default=70, ge=0, le=100)
    ux_score: int = Field(default=70, ge=0, le=100)
    seo_score: int = Field(default=70, ge=0, le=100)
    conversion_score: int = Field(default=70, ge=0, le=100)
    accessibility_score: int = Field(default=70, ge=0, le=100)


class WebsiteOpportunityBreakdown(BaseModel):
    """Deterministic opportunity score breakdown (0-100)."""
    performance_opportunity: int = Field(default=0, ge=0, le=20)
    mobile_opportunity: int = Field(default=0, ge=0, le=15)
    ux_opportunity: int = Field(default=0, ge=0, le=15)
    seo_opportunity: int = Field(default=0, ge=0, le=15)
    conversion_opportunity: int = Field(default=0, ge=0, le=15)
    ecommerce_opportunity: int = Field(default=0, ge=0, le=10)
    tech_modernization_opportunity: int = Field(default=0, ge=0, le=10)
    total_opportunity_score: int = Field(default=0, ge=0, le=100)
    reasons: List[str] = Field(default_factory=list)


class WebsiteResearchSummary(BaseModel):
    """High-level synthesis of website research findings."""
    website_status: str
    business_summary: str
    technology_summary: str
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    opportunities: List[str] = Field(default_factory=list)
    critical_findings: List[str] = Field(default_factory=list)
    recommended_service: str
    alternative_services: List[str] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
