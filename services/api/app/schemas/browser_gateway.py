import uuid
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class PairingChallengeResponse(BaseModel):
    pairing_code: str
    expires_in_seconds: int
    expires_at: str


class PairRequest(BaseModel):
    pairing_code: str = Field(..., min_length=4, max_length=32)
    browser_id: str = Field(..., min_length=1, max_length=255)
    session_id: Optional[uuid.UUID] = None
    client_version: str = Field(default="2.0.0")


class PairResponse(BaseModel):
    session_id: uuid.UUID
    token: str
    organization_id: uuid.UUID
    expires_at: str


class RevokeRequest(BaseModel):
    session_id: uuid.UUID


class BrowserStatusResponse(BaseModel):
    session_id: Optional[uuid.UUID] = None
    organization_id: uuid.UUID
    is_connected: bool
    session_state: str
    current_url: Optional[str] = None
    current_domain: Optional[str] = None
    page_type: Optional[str] = None


class SessionControlRequest(BaseModel):
    session_id: uuid.UUID
    reason: Optional[str] = None


class ExecuteApprovedOutreachRequest(BaseModel):
    session_id: uuid.UUID
    lead_id: uuid.UUID
    draft_id: uuid.UUID
    approval_id: Optional[uuid.UUID] = None
