import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ResearchInitiateRequest(BaseModel):
    website_url: Optional[str] = Field(None, description="Optional override for the website URL")
    force_recheck: bool = Field(False, description="Whether to bypass cache and re-run analysis")
    pages_data: Optional[List[Dict[str, Any]]] = Field(None, description="Optional pre-observed browser page dumps")


class WebsitePageResearchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    research_id: uuid.UUID
    organization_id: uuid.UUID
    url: str
    page_type: str
    title: Optional[str] = None
    status_code: Optional[int] = None
    content_summary: Optional[str] = None
    links_count: int = 0
    has_cta: bool = False
    has_contact_form: bool = False
    has_phone: bool = False
    has_email: bool = False
    has_pricing: bool = False
    has_product_catalog: bool = False
    has_checkout: bool = False
    has_social_proof: bool = False
    mobile_observations: List[str] = Field(default_factory=list)
    ux_observations: List[str] = Field(default_factory=list)
    seo_observations: List[str] = Field(default_factory=list)
    performance_observations: List[str] = Field(default_factory=list)
    conversion_observations: List[str] = Field(default_factory=list)
    created_at: datetime


class TechnologyStackResponse(BaseModel):
    technology_stack: List[Dict[str, Any]] = Field(default_factory=list)
    cms: Optional[str] = None
    frontend_framework: Optional[str] = None
    backend_technology: Optional[str] = None
    analytics_tools: List[str] = Field(default_factory=list)
    payment_provider: Optional[str] = None
    hosting_provider: Optional[str] = None
    cdn: Optional[str] = None
    ecommerce_platform: Optional[str] = None


class WebsiteAuditResponse(BaseModel):
    website_health_score: Optional[int] = None
    performance_score: Optional[int] = None
    mobile_score: Optional[int] = None
    ux_score: Optional[int] = None
    seo_score: Optional[int] = None
    conversion_score: Optional[int] = None
    accessibility_score: Optional[int] = None
    positive_findings: List[str] = Field(default_factory=list)
    negative_findings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class WebsiteOpportunityResponse(BaseModel):
    opportunity_score: Optional[int] = None
    breakdown: Optional[Dict[str, Any]] = None
    reasons: List[str] = Field(default_factory=list)


class WebsiteResearchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    lead_id: uuid.UUID
    company_id: Optional[uuid.UUID] = None
    website_url: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    pages_analyzed: int = 0
    pages_failed: int = 0

    technology_stack: List[Dict[str, Any]] = Field(default_factory=list)
    cms: Optional[str] = None
    frontend_framework: Optional[str] = None
    backend_technology: Optional[str] = None
    analytics_tools: List[str] = Field(default_factory=list)
    payment_provider: Optional[str] = None
    hosting_provider: Optional[str] = None
    cdn: Optional[str] = None
    ecommerce_platform: Optional[str] = None

    website_health_score: Optional[int] = None
    performance_score: Optional[int] = None
    mobile_score: Optional[int] = None
    ux_score: Optional[int] = None
    seo_score: Optional[int] = None
    conversion_score: Optional[int] = None
    accessibility_score: Optional[int] = None
    opportunity_score: Optional[int] = None

    summary: Optional[str] = None
    positive_findings: List[str] = Field(default_factory=list)
    negative_findings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    confidence: float = 0.0

    created_at: datetime
    updated_at: datetime
