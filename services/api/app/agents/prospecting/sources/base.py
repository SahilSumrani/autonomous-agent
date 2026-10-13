import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from packages.shared_types.prospecting import CandidateStatus, ProspectingSourceType


class UnsupportedSourceException(ValueError):
    """Raised when a requested prospecting source does not have a dedicated adapter."""
    pass


class DiscoveredCandidateItem(BaseModel):
    """Raw candidate discovered on a source page."""
    source_url: str
    canonical_url: Optional[str] = None
    platform: str
    username_or_handle: Optional[str] = None
    company_name: Optional[str] = None
    domain: Optional[str] = None
    business_category: Optional[str] = None
    evidence: str
    confidence: float = 0.5
    raw_payload: Dict[str, Any] = Field(default_factory=dict)


class SecurityChallengeResult(BaseModel):
    """Result of checking a page observation for security challenges / blockers."""
    is_blocked: bool
    challenge_type: Optional[str] = None  # CAPTCHA, LOGIN_REQUIRED, RATE_LIMITED, BLOCKED_IP
    reason: Optional[str] = None


class BrowserActionStep(BaseModel):
    """Next action recommended by a source adapter."""
    action_type: str  # OPEN_PAGE, SCROLL, READ_PAGE, CLICK
    url: Optional[str] = None
    selector: Optional[str] = None
    description: str


# Common security wall patterns across platforms
GLOBAL_BLOCK_PATTERNS = [
    (r"cf-browser-verification|challenge-running|turnstile|recaptcha|hcaptcha|bot detection", "CAPTCHA"),
    (r"access denied|403 forbidden|error 1020|you have been blocked|request blocked", "BLOCKED_IP"),
    (r"rate limit exceeded|too many requests|429 too many requests|slow down", "RATE_LIMITED"),
]


class ProspectingSource(ABC):
    """Abstract base class for all prospecting platform adapters."""

    source_type: ProspectingSourceType

    @abstractmethod
    def get_initial_url(self, query: Optional[str]) -> str:
        """Return entry URL for the given job query."""
        pass

    def get_entry_urls(self, query: Optional[str] = None, profile: Optional[Any] = None) -> List[str]:
        """Return list of entry URLs for the given query or prospecting profile."""
        init = self.get_initial_url(query)
        return [init] if init else []


    @abstractmethod
    def detect_security_challenge(self, page_data: Dict[str, Any]) -> SecurityChallengeResult:
        """Check if page displays a CAPTCHA, login barrier, rate-limit, or security challenge."""
        pass

    @abstractmethod
    def discover_candidates(
        self,
        page_data: Dict[str, Any],
        query: Optional[str] = None,
    ) -> List[DiscoveredCandidateItem]:
        """Parse visible content and identify potential prospect candidates."""
        pass

    @abstractmethod
    def build_dedup_key(self, candidate: DiscoveredCandidateItem) -> str:
        """Generate a deterministic, unique deduplication key for this candidate."""
        pass

    def next_urls(self, page_data: Dict[str, Any], query: Optional[str] = None) -> List[str]:
        """Extract subsequent URLs to visit from observed page data (permalinks, pagination, related links)."""
        return []

    def check_common_blockers(self, text: str, title: Optional[str] = None) -> Optional[SecurityChallengeResult]:
        content = f"{title or ''} {text}".lower()
        for pattern, challenge_type in GLOBAL_BLOCK_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                return SecurityChallengeResult(
                    is_blocked=True,
                    challenge_type=challenge_type,
                    reason=f"Platform security challenge detected: {challenge_type}",
                )
        return None
