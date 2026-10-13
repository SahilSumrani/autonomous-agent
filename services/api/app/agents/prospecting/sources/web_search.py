import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from packages.shared_types.prospecting import ProspectingSourceType
from services.api.app.agents.prospecting.sources.base import (
    DiscoveredCandidateItem,
    ProspectingSource,
    SecurityChallengeResult,
)
from services.api.app.services.normalization import normalize_domain

SEARCH_CHALLENGE_PATTERNS = [
    r"our systems have detected unusual traffic",
    r"please verify that you're not a robot",
    r"solve this challenge to continue",
]


class WebSearchSource(ProspectingSource):
    source_type = ProspectingSourceType.WEB_SEARCH

    def get_initial_url(self, query: Optional[str]) -> str:
        if not query:
            return "https://duckduckgo.com/html/?q=small+business+need+website"
        clean = query.strip()
        if clean.startswith("http://") or clean.startswith("https://"):
            return clean
        encoded = clean.replace(" ", "+")
        # Use simple HTML search URL
        return f"https://duckduckgo.com/html/?q={encoded}"

    def get_entry_urls(self, query: Optional[str] = None, profile: Optional[Any] = None) -> List[str]:
        if query and query.strip():
            return [self.get_initial_url(query)]
        keywords = []
        if profile and hasattr(profile, "ideal_customer_keywords") and profile.ideal_customer_keywords:
            keywords = profile.ideal_customer_keywords
        else:
            keywords = ["small business need website", "hire web developer"]

        urls = []
        for kw in keywords:
            encoded = kw.strip().replace(" ", "+")
            if encoded:
                urls.append(f"https://duckduckgo.com/html/?q={encoded}")
        return urls or ["https://duckduckgo.com/html/?q=small+business+need+website"]

    def detect_security_challenge(self, page_data: Dict[str, Any]) -> SecurityChallengeResult:
        text = page_data.get("visible_text") or ""
        title = page_data.get("page_title") or ""
        common = self.check_common_blockers(text, title)
        if common:
            return common

        combined = f"{title} {text}".lower()
        for pat in SEARCH_CHALLENGE_PATTERNS:
            if re.search(pat, combined, re.IGNORECASE):
                return SecurityChallengeResult(
                    is_blocked=True,
                    challenge_type="CAPTCHA",
                    reason=f"Search engine challenge detected: {pat}",
                )

        return SecurityChallengeResult(is_blocked=False)

    def discover_candidates(
        self,
        page_data: Dict[str, Any],
        query: Optional[str] = None,
    ) -> List[DiscoveredCandidateItem]:
        links = page_data.get("links") or []
        candidates: List[DiscoveredCandidateItem] = []
        seen_domains = set()

        # Extract external non-search links
        for link in links:
            if not isinstance(link, str) or not (link.startswith("http://") or link.startswith("https://")):
                continue
            parsed = urlparse(link)
            netloc = parsed.netloc.lower()
            if any(ign in netloc for ign in ("duckduckgo.com", "google.com", "bing.com", "yahoo.com")):
                continue
            dom = normalize_domain(link)
            if dom and dom not in seen_domains:
                seen_domains.add(dom)
                candidates.append(
                    DiscoveredCandidateItem(
                        source_url=link,
                        canonical_url=f"https://{dom}",
                        platform="WEB_SEARCH",
                        company_name=dom,
                        domain=dom,
                        evidence=f"Discovered via web search at {link}",
                        confidence=0.7,
                        raw_payload={"url": link, "domain": dom},
                    )
                )

        return candidates

    def build_dedup_key(self, candidate: DiscoveredCandidateItem) -> str:
        dom = candidate.domain or normalize_domain(candidate.source_url)
        if dom:
            return f"domain:{dom}"
        return f"url:{candidate.source_url}"

    def next_urls(self, page_data: Dict[str, Any], query: Optional[str] = None) -> List[str]:
        links = page_data.get("links") or []
        urls: List[str] = []
        seen = set()

        for link in links:
            if not isinstance(link, str) or not link.startswith("http"):
                continue
            # Next pagination link or external search result link
            dom = normalize_domain(link)
            if dom and not any(eng in dom for eng in ["google.", "bing.", "duckduckgo.", "yahoo."]):
                clean = link.split("#")[0]
                if clean not in seen:
                    seen.add(clean)
                    urls.append(clean)
            elif "duckduckgo.com" in link and ("&s=" in link or "next" in link.lower()):
                if link not in seen:
                    seen.add(link)
                    urls.append(link)

        return urls
