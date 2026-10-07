import uuid
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from packages.shared_types.crm import (
    ActorType,
    CompanyStatus,
    LeadStatus,
    LeadType,
    SignalType,
    SourceType,
    UserRole,
)

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    page: int
    page_size: int
    total: int
    total_pages: int


# --- Organization ---
class OrganizationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=255)


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationResponse(OrganizationBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- User ---
class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    role: UserRole = UserRole.MEMBER
    is_active: bool = True


class UserCreate(UserBase):
    organization_id: uuid.UUID


class UserResponse(UserBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Company ---
class CompanyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    domain: Optional[str] = None
    description: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None
    country: Optional[str] = None
    website_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    instagram_url: Optional[str] = None
    reddit_url: Optional[str] = None
    status: CompanyStatus = CompanyStatus.UNKNOWN
    metadata_json: Optional[Dict[str, Any]] = None


class CompanyCreate(CompanyBase):
    organization_id: uuid.UUID


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    domain: Optional[str] = None
    description: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None
    country: Optional[str] = None
    website_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    instagram_url: Optional[str] = None
    reddit_url: Optional[str] = None
    status: Optional[CompanyStatus] = None
    metadata_json: Optional[Dict[str, Any]] = None


class CompanyResponse(CompanyBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    normalized_name: str
    normalized_domain: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Contact ---
class ContactBase(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    job_title: Optional[str] = None
    email: Optional[EmailStr] = None
    email_verified: bool = False
    phone: Optional[str] = None
    instagram_username: Optional[str] = None
    instagram_url: Optional[str] = None
    reddit_username: Optional[str] = None
    reddit_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    location: Optional[str] = None


class ContactCreate(ContactBase):
    organization_id: uuid.UUID
    company_id: Optional[uuid.UUID] = None


class ContactUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    job_title: Optional[str] = None
    email: Optional[EmailStr] = None
    email_verified: Optional[bool] = None
    phone: Optional[str] = None
    instagram_username: Optional[str] = None
    instagram_url: Optional[str] = None
    reddit_username: Optional[str] = None
    reddit_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    location: Optional[str] = None
    company_id: Optional[uuid.UUID] = None


class ContactResponse(ContactBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    company_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- LeadSource ---
class LeadSourceCreate(BaseModel):
    organization_id: uuid.UUID
    source_type: SourceType = SourceType.WEB
    source_name: str = Field(..., min_length=1, max_length=255)
    source_url: Optional[str] = None
    external_id: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None


class LeadSourceResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    source_type: SourceType
    source_name: str
    source_url: Optional[str] = None
    external_id: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Lead ---
class LeadBase(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    lead_type: LeadType = LeadType.COMPANY
    source_url: Optional[str] = None
    profile_url: Optional[str] = None
    content_url: Optional[str] = None
    intent_score: int = Field(default=0, ge=0, le=100)
    qualification_score: int = Field(default=0, ge=0, le=100)
    overall_score: int = Field(default=0, ge=0, le=100)
    recommended_service: Optional[str] = None


class LeadCreate(LeadBase):
    organization_id: uuid.UUID
    company_id: Optional[uuid.UUID] = None
    contact_id: Optional[uuid.UUID] = None
    source_id: Optional[uuid.UUID] = None
    status: LeadStatus = LeadStatus.NEW


class LeadUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    lead_type: Optional[LeadType] = None
    company_id: Optional[uuid.UUID] = None
    contact_id: Optional[uuid.UUID] = None
    source_id: Optional[uuid.UUID] = None
    source_url: Optional[str] = None
    profile_url: Optional[str] = None
    content_url: Optional[str] = None
    intent_score: Optional[int] = Field(None, ge=0, le=100)
    qualification_score: Optional[int] = Field(None, ge=0, le=100)
    overall_score: Optional[int] = Field(None, ge=0, le=100)
    recommended_service: Optional[str] = None


class LeadStatusUpdate(BaseModel):
    new_status: LeadStatus
    reason: Optional[str] = None
    actor_type: ActorType = ActorType.USER
    actor_id: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None


class LeadResponse(LeadBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    company_id: Optional[uuid.UUID] = None
    contact_id: Optional[uuid.UUID] = None
    source_id: Optional[uuid.UUID] = None
    status: LeadStatus
    first_seen_at: datetime
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- LeadSignal ---
class LeadSignalCreate(BaseModel):
    lead_id: uuid.UUID
    signal_type: SignalType
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: str = Field(..., min_length=1)
    source_url: Optional[str] = None
    detected_at: Optional[datetime] = None


class LeadSignalResponse(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    signal_type: str
    confidence: float
    evidence: str
    source_url: Optional[str] = None
    detected_at: datetime
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- PipelineEvent ---
class PipelineEventResponse(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    old_status: Optional[str] = None
    new_status: str
    actor_type: str
    actor_id: Optional[str] = None
    reason: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
