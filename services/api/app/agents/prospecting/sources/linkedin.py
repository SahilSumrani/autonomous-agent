"""
LinkedIn Source Adapter (Read-Only Human Session Observation).

LEGAL & COMPLIANCE NOTICE:
Automated interaction with LinkedIn may violate LinkedIn's User Agreement and Terms of Service,
and carries a potential risk of account restriction or suspension.
This adapter is strictly read-only: it observes only visible content rendered in the user's
own authenticated browser tab, enforces conservative request boundaries, strictly avoids profile crawling,
and immediately halts upon encountering any authentication challenge or security checkpoint.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from packages.shared_types.prospecting import ProspectingSourceType
from services.api.app.agents.prospecting.sources.base import (
    DiscoveredCandidateItem,
    ProspectingSource,
    SecurityChallengeResult,
)
from services.api.app.agents.signals.engine import SignalDetectionEngine
from services.api.app.services.normalization import (
    is_disallowed_business_domain,
    is_platform_owned_domain,
    normalize_domain,
    normalize_username,
)

logger = logging.getLogger("techverse.agent.prospecting.sources.linkedin")

LINKEDIN_CHALLENGE_PATTERNS = [
    r"authwall",
    r"checkpoint/challenge",
    r"security verification",
    r"verify your account",
    r"unusual activity",
    r"quick security check",
    r"join linkedin",
    r"sign in to see more",
    r"please enter the code sent",
    r"prove you are human",
]


class LinkedInSource(ProspectingSource):
    """
    Read-only LinkedIn adapter.
    Operates strictly on the visible feed in the user's active logged-in Chrome session.
    Never navigates to personal profiles or external scraping endpoints.
    """

    source_type = ProspectingSourceType.LINKEDIN

    def get_initial_url(self, query: Optional[str]) -> str:
        if not query:
            return "https://www.linkedin.com/feed/"
        clean = query.strip()
        if clean.startswith("http://") or clean.startswith("https://"):
            return clean
        # Keyword search within content feed
        encoded = clean.replace(" ", "%20")
        return f"https://www.linkedin.com/search/results/content/?keywords={encoded}&origin=GLOBAL_SEARCH_HEADER"

    def get_entry_urls(self, query: Optional[str] = None, profile: Optional[Any] = None) -> List[str]:
        if query and query.strip():
            return [self.get_initial_url(query)]
        urls = ["https://www.linkedin.com/feed/"]
        keywords = []
        if profile and hasattr(profile, "ideal_customer_keywords") and profile.ideal_customer_keywords:
            keywords = profile.ideal_customer_keywords
        else:
            keywords = ["need a website", "looking for developer"]

        for kw in keywords:
            encoded = kw.strip().replace(" ", "%20")
            if encoded:
                urls.append(f"https://www.linkedin.com/search/results/content/?keywords={encoded}&origin=GLOBAL_SEARCH_HEADER")
        return urls

    def detect_security_challenge(self, page_data: Dict[str, Any]) -> SecurityChallengeResult:
        text = page_data.get("visible_text") or ""
        title = page_data.get("page_title") or ""
        url = page_data.get("url") or ""

        common = self.check_common_blockers(text, title)
        if common:
            return common

        combined = f"{url} {title} {text}".lower()
        for pat in LINKEDIN_CHALLENGE_PATTERNS:
            if re.search(pat, combined, re.IGNORECASE):
                logger.warning(f"LinkedIn security barrier detected: {pat}")
                return SecurityChallengeResult(
                    is_blocked=True,
                    challenge_type="LOGIN_REQUIRED" if "sign in" in pat or "authwall" in pat else "CAPTCHA",
                    reason=f"LinkedIn security checkpoint detected: '{pat}'. Human operator must resolve in browser.",
                )

        return SecurityChallengeResult(is_blocked=False)

    def discover_candidates(
        self,
        page_data: Dict[str, Any],
        query: Optional[str] = None,
    ) -> List[DiscoveredCandidateItem]:
        text = page_data.get("visible_text") or ""
        url = page_data.get("url") or ""
        candidates: List[DiscoveredCandidateItem] = []
        seen_posts = set()

        # 1. Process structured content units extracted from feed update elements
        structured_posts = page_data.get("posts") or page_data.get("content_units") or []
        for post in structured_posts:
            if isinstance(post, dict):
                raw_author = (post.get("author") or "").strip()
                # Reject anonymous or generic LinkedIn member placeholders
                if not raw_author or raw_author.lower() in ("linkedin member", "discovered prospect", "anonymous"):
                    continue

                p_text = (post.get("text") or post.get("body") or "").strip()
                p_url = post.get("url") or url
                links = post.get("links") or []

                if len(p_text) < 15:
                    continue

                # Anti-false positive check & signal detection
                if SignalDetectionEngine.check_false_positive(p_text):
                    continue
                signals = SignalDetectionEngine.detect_signals(p_text, source_url=p_url)
                if not signals:
                    continue

                # Per-post deduplication key
                post_match = re.search(r"(?:urn:li:activity:|posts/)([0-9a-zA-Z_-]+)", p_url)
                post_id = post_match.group(1) if post_match else f"{raw_author}:{p_text[:40]}"
                if post_id in seen_posts:
                    continue
                seen_posts.add(post_id)

                # Never set domain to linkedin.com, email providers, or placeholders
                domain = None
                for link in links:
                    if isinstance(link, str):
                        ld = normalize_domain(link)
                        if ld and not is_disallowed_business_domain(ld):
                            domain = ld
                            break

                norm_user = normalize_username(raw_author)
                handle_str = norm_user.replace(" ", "_") if norm_user else None
                candidates.append(
                    DiscoveredCandidateItem(
                        source_url=p_url,
                        canonical_url=p_url,
                        platform="LINKEDIN",
                        username_or_handle=f"in/{handle_str}" if handle_str else None,
                        company_name=raw_author,
                        domain=domain,
                        evidence=f"Visible LinkedIn post by {raw_author}: '{p_text[:300]}'",
                        confidence=signals[0].confidence,
                        raw_payload={"author": raw_author, "post_id": post_id, "url": p_url, "text": p_text},
                    )
                )

        # 2. Fallback text parsing ONLY if an attributable author is explicitly identifiable
        if not candidates and len(text) > 40:
            author_match = re.search(r"(?:^|\n)([A-Z][a-zA-Z\s]{2,40})\s+(?:•\s*(?:1st|2nd|3rd|Following)|View profile)", text)
            if author_match and not SignalDetectionEngine.check_false_positive(text):
                fallback_author = author_match.group(1).strip()
                if fallback_author.lower() not in ("linkedin member", "discovered prospect"):
                    signals = SignalDetectionEngine.detect_signals(text, source_url=url)
                    if signals:
                        domain_match = re.search(r"\b([a-zA-Z0-9-]+\.(?:com|org|io|co|ai|net|store))\b", text, re.IGNORECASE)
                        domain = None
                        if domain_match:
                            pot_dom = normalize_domain(domain_match.group(1))
                            if pot_dom and not is_disallowed_business_domain(pot_dom):
                                domain = pot_dom

                        norm_user = normalize_username(fallback_author)
                        handle_str = norm_user.replace(" ", "_") if norm_user else None
                        candidates.append(
                            DiscoveredCandidateItem(
                                source_url=url,
                                canonical_url=url,
                                platform="LINKEDIN",
                                username_or_handle=f"in/{handle_str}" if handle_str else None,
                                company_name=fallback_author,
                                domain=domain,
                                evidence=f"Observed LinkedIn post by {fallback_author}: {signals[0].evidence}",
                                confidence=signals[0].confidence,
                                raw_payload={"author": fallback_author, "url": url, "signal": signals[0].signal_type.value},
                            )
                        )

        return candidates

    def build_dedup_key(self, candidate: DiscoveredCandidateItem) -> str:
        # Deduplicate by LinkedIn activity / update ID
        match = re.search(r"(?:urn:li:activity:|posts/)([0-9a-zA-Z_-]+)", candidate.source_url)
        if match:
            return f"linkedin_post:{match.group(1)}"
        if candidate.username_or_handle:
            return f"linkedin_author:{candidate.username_or_handle}"
        return f"url:{candidate.source_url}"

    def next_urls(self, page_data: Dict[str, Any], query: Optional[str] = None) -> List[str]:
        # Strict security constraint: no profile crawling or arbitrary link recursion on LinkedIn
        return []
