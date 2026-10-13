import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from packages.shared_types.prospecting import ProspectingSourceType
from services.api.app.agents.prospecting.sources.base import (
    DiscoveredCandidateItem,
    ProspectingSource,
    SecurityChallengeResult,
)
from services.api.app.agents.signals.engine import SignalDetectionEngine
from services.api.app.services.normalization import (
    is_disallowed_business_domain,
    normalize_company_name,
    normalize_domain,
)


class WebsiteSource(ProspectingSource):
    source_type = ProspectingSourceType.WEBSITE

    def get_initial_url(self, query: Optional[str]) -> str:
        if not query or not query.strip():
            return ""
        clean = query.strip()
        if clean.startswith("http://") or clean.startswith("https://"):
            return clean
        return f"https://{clean}"

    def detect_security_challenge(self, page_data: Dict[str, Any]) -> SecurityChallengeResult:
        text = page_data.get("visible_text") or ""
        title = page_data.get("page_title") or ""
        common = self.check_common_blockers(text, title)
        if common:
            return common
        return SecurityChallengeResult(is_blocked=False)

    def discover_candidates(
        self,
        page_data: Dict[str, Any],
        query: Optional[str] = None,
    ) -> List[DiscoveredCandidateItem]:
        text = page_data.get("visible_text") or ""
        url = page_data.get("url") or ""
        title = page_data.get("page_title") or ""

        domain = normalize_domain(url)
        if not domain or is_disallowed_business_domain(domain):
            return []

        # Anti-false-positive check: do not discover competitors, job seekers, students
        if SignalDetectionEngine.check_false_positive(text):
            return []

        # Derive candidate company name cleanly from title or domain
        clean_title = re.sub(r"[-|•].*$", "", title).strip()
        name = clean_title if (clean_title and len(clean_title) < 60) else domain

        # Require genuine commercial or technical signal (e.g. outdated site, migration, hiring)
        signals = SignalDetectionEngine.detect_signals(text, source_url=url, website_text=text)
        if not signals:
            return []

        primary_sig = signals[0]
        candidate = DiscoveredCandidateItem(
            source_url=url,
            canonical_url=f"https://{domain}",
            platform="WEBSITE",
            company_name=name,
            domain=domain,
            evidence=f"Direct website exploration at {url}. Signal: {primary_sig.evidence}",
            confidence=primary_sig.confidence,
            raw_payload={
                "url": url,
                "domain": domain,
                "title": title,
                "signal": primary_sig.signal_type.value,
            },
        )
        return [candidate]

    def build_dedup_key(self, candidate: DiscoveredCandidateItem) -> str:
        dom = candidate.domain or normalize_domain(candidate.source_url)
        if dom:
            return f"domain:{dom}"
        return f"url:{candidate.source_url}"

    def next_urls(self, page_data: Dict[str, Any], query: Optional[str] = None) -> List[str]:
        curr_url = page_data.get("url") or ""
        base_dom = normalize_domain(curr_url)
        if not base_dom:
            return []

        links = page_data.get("links") or []
        urls: List[str] = []
        seen = set()

        # Prioritize relevant prospecting subpages
        priority_keywords = ["about", "contact", "services", "team", "product", "pricing", "catalog", "portfolio", "blog"]
        priority_urls = []
        regular_urls = []

        for link in links:
            if not isinstance(link, str) or not link.startswith("http"):
                continue
            link_dom = normalize_domain(link)
            if link_dom == base_dom:
                clean = link.split("#")[0]
                if clean not in seen and clean != curr_url:
                    seen.add(clean)
                    if any(kw in clean.lower() for kw in priority_keywords):
                        priority_urls.append(clean)
                    else:
                        regular_urls.append(clean)

        return priority_urls + regular_urls
