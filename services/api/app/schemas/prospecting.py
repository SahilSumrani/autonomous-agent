import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from packages.shared_types.prospecting import (
    CandidateStatus,
    ProspectingJobEndReason,
    ProspectingJobStatus,
    ProspectingSourceType,
    QualificationLevel,
)


class ProspectingJobCreate(BaseModel):
    source: ProspectingSourceType = Field(default=ProspectingSourceType.WEBSITE)
    query: Optional[str] = Field(None, max_length=1000, description="Entry URL, subreddit, search query, or hashtag")
    target_service: Optional[str] = Field(None, max_length=255)
    target_industries: Optional[List[str]] = Field(default_factory=list)
    target_geography: Optional[str] = Field(None, max_length=255)
    max_candidates: int = Field(default=10, ge=1, le=50)
    max_pages: int = Field(default=50, ge=1, le=200)
    max_scrolls: int = Field(default=5, ge=1, le=20)
    max_time_seconds: int = Field(default=1800, ge=60, le=7200)
    session_id: Optional[uuid.UUID] = Field(None, description="Bound browser agent session id if pre-existing")
    metadata: Optional[Dict[str, Any]] = None


class ProspectingJobResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    session_id: Optional[uuid.UUID] = None
    status: ProspectingJobStatus
    source: ProspectingSourceType
    query: Optional[str] = None
    target_service: Optional[str] = None
    target_industries: Optional[List[str]] = None
    target_geography: Optional[str] = None
    max_candidates: int
    max_pages: int
    max_scrolls: int
    max_time_seconds: int
    end_reason: Optional[ProspectingJobEndReason] = None
    failure_reason: Optional[str] = None
    statistics: Dict[str, Any] = Field(default_factory=dict)
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProspectCandidateResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    organization_id: uuid.UUID
    source: str
    source_url: Optional[str] = None
    canonical_url: Optional[str] = None
    platform: str
    username_or_handle: Optional[str] = None
    company_name: Optional[str] = None
    domain: Optional[str] = None
    business_category: Optional[str] = None
    location: Optional[str] = None
    discovery_evidence: Optional[str] = None
    status: CandidateStatus
    confidence: float
    dedup_key: str
    linked_lead_id: Optional[uuid.UUID] = None
    first_seen: datetime
    last_seen: datetime
    metadata_json: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class ProspectObservationResponse(BaseModel):
    id: uuid.UUID
    job_id: Optional[uuid.UUID] = None
    candidate_id: Optional[uuid.UUID] = None
    session_id: Optional[uuid.UUID] = None
    organization_id: uuid.UUID
    url: str
    platform: str
    page_title: Optional[str] = None
    visible_text_snippet: Optional[str] = None
    headings: Optional[List[str]] = None
    content_hash: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ProspectingProfileRead(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    services_offered: List[str]
    ideal_customer_keywords: List[str]
    excluded_keywords: List[str]
    sources_enabled: List[str]
    daily_limits_json: Dict[str, int]
    geography: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProspectingProfileUpdate(BaseModel):
    services_offered: Optional[List[str]] = None
    ideal_customer_keywords: Optional[List[str]] = None
    excluded_keywords: Optional[List[str]] = None
    sources_enabled: Optional[List[str]] = None
    daily_limits_json: Optional[Dict[str, int]] = None
    geography: Optional[str] = None

