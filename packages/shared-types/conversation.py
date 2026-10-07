import enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ThreadStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    WAITING_FOR_REPLY = "WAITING_FOR_REPLY"
    NEEDS_HUMAN = "NEEDS_HUMAN"
    CLOSED = "CLOSED"
    BLOCKED = "BLOCKED"


class MessageDirection(str, enum.Enum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class MessageAuthorType(str, enum.Enum):
    PROSPECT = "PROSPECT"
    AGENT = "AGENT"
    USER = "USER"


class MessageDeliveryStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"
    DRAFTED = "DRAFTED"
    APPROVED = "APPROVED"
    SENT = "SENT"
    DELIVERY_UNKNOWN = "DELIVERY_UNKNOWN"
    FAILED = "FAILED"


class SalesStage(str, enum.Enum):
    CONTACTED = "CONTACTED"
    REPLIED = "REPLIED"
    QUALIFIED_CONVERSATION = "QUALIFIED_CONVERSATION"
    INTERESTED = "INTERESTED"
    MEETING_REQUESTED = "MEETING_REQUESTED"
    MEETING_SCHEDULED = "MEETING_SCHEDULED"
    PROPOSAL_READY = "PROPOSAL_READY"
    WON = "WON"
    LOST = "LOST"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class ProspectIntent(str, enum.Enum):
    INTERESTED = "INTERESTED"
    HIGH_INTEREST = "HIGH_INTEREST"
    PRICING_REQUEST = "PRICING_REQUEST"
    PORTFOLIO_REQUEST = "PORTFOLIO_REQUEST"
    SERVICE_DETAILS = "SERVICE_DETAILS"
    MEETING_REQUEST = "MEETING_REQUEST"
    NOT_INTERESTED = "NOT_INTERESTED"
    FOLLOW_UP_LATER = "FOLLOW_UP_LATER"
    EXISTING_VENDOR = "EXISTING_VENDOR"
    WRONG_PERSON = "WRONG_PERSON"
    OBJECTION = "OBJECTION"
    QUESTION = "QUESTION"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    SPAM_OR_BOT = "SPAM_OR_BOT"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    UNKNOWN = "UNKNOWN"


class ReplyObjective(str, enum.Enum):
    ANSWER = "ANSWER"
    CLARIFY = "CLARIFY"
    QUALIFY = "QUALIFY"
    REQUEST_DETAILS = "REQUEST_DETAILS"
    SHARE_PORTFOLIO = "SHARE_PORTFOLIO"
    REQUEST_MEETING = "REQUEST_MEETING"
    HANDLE_OBJECTION = "HANDLE_OBJECTION"
    FOLLOW_UP = "FOLLOW_UP"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    DO_NOT_REPLY = "DO_NOT_REPLY"


class ReplyApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"


class IntentClassificationResult(BaseModel):
    intent: ProspectIntent
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: str
    reasoning: str
    classifier_version: str = "v1_deterministic"
    created_at: Optional[float] = None


class ObjectionClassification(BaseModel):
    objection_type: str
    severity: str
    recommended_strategy: str
    do_not_claim: List[str] = Field(default_factory=list)
    requires_human_approval: bool = True
