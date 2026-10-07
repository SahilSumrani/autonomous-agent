import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BrowserCommandType(str, Enum):
    OPEN_PAGE = "OPEN_PAGE"
    NAVIGATE = "NAVIGATE"
    READ_PAGE = "READ_PAGE"
    FIND_TEXT = "FIND_TEXT"
    SCROLL = "SCROLL"
    CLICK = "CLICK"
    EXTRACT_VISIBLE_CONTENT = "EXTRACT_VISIBLE_CONTENT"
    EXTRACT_LINKS = "EXTRACT_LINKS"
    GET_PAGE_STATE = "GET_PAGE_STATE"
    REQUEST_USER_APPROVAL = "REQUEST_USER_APPROVAL"
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    STOP = "STOP"
    EXECUTE_APPROVED_OUTREACH = "EXECUTE_APPROVED_OUTREACH"


class CommandExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    DELIVERY_UNKNOWN = "DELIVERY_UNKNOWN"


class ExtensionSessionState(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    AUTHORIZED = "AUTHORIZED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    BLOCKED = "BLOCKED"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class PageType(str, Enum):
    INSTAGRAM_POST = "INSTAGRAM_POST"
    INSTAGRAM_PROFILE = "INSTAGRAM_PROFILE"
    REDDIT_POST = "REDDIT_POST"
    REDDIT_PROFILE = "REDDIT_PROFILE"
    PUBLIC_WEBSITE = "PUBLIC_WEBSITE"
    SEARCH_ENGINE = "SEARCH_ENGINE"
    OTHER = "OTHER"
    BLOCKED_PAGE = "BLOCKED_PAGE"


class BrowserCommand(BaseModel):
    command_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    session_id: uuid.UUID
    type: BrowserCommandType
    payload: Dict[str, Any] = Field(default_factory=dict)
    issued_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class BrowserCommandResult(BaseModel):
    command_id: uuid.UUID
    session_id: uuid.UUID
    success: bool
    status: CommandExecutionStatus
    result: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    duration_ms: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str


class PageState(BaseModel):
    url: str
    title: Optional[str] = None
    origin: Optional[str] = None
    page_type: PageType = PageType.OTHER
    is_loading: bool = False
    visible_text_available: bool = True
    interactive_elements_count: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ClickTarget(BaseModel):
    selector_type: str = Field(default="text", description="'text', 'selector', or 'id'")
    value: str
    description: Optional[str] = None


class ExecuteApprovedOutreachPayload(BaseModel):
    draft_id: uuid.UUID
    lead_id: uuid.UUID
    channel: str
    recipient: str
    subject: Optional[str] = None
    body: str
    cta_text: Optional[str] = None
    approval_id: uuid.UUID
    expected_profile_or_domain: Optional[str] = None
