import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from services.api.app.agents.research.evidence_collector import EvidenceCollector
from services.api.app.agents.research.page_analyzer import PageAnalyzer
from services.api.app.agents.research.research_models import (
    EvidenceCategory,
    PageAnalysisResult,
    ResearchEvidence,
    WebsiteResolution,
)
from services.api.app.agents.research.validators import (
    SSRFValidationError,
    validate_and_sanitize_target_url,
)

MAX_PAGES_PER_RESEARCH = 10
RELEVANT_PATH_KEYWORDS = [
    "about", "service", "product", "pricing", "shop", "store",
    "contact", "portfolio", "case-study", "blog"
]


class WebsiteResearcher:
    """Discovers, resolves, navigates, and analyzes public pages for a lead's website."""

    @classmethod
    def resolve_website(
        cls,
        company_domain: Optional[str] = None,
        profile_url: Optional[str] = None,
        source_url: Optional[str] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
    ) -> WebsiteResolution:
        candidates: List[str] = []
        evidence_collector = EvidenceCollector()

        # 1. Check direct company domain
        if company_domain:
            candidates.append(company_domain)
            evidence_collector.add_evidence(
                category=EvidenceCategory.BUSINESS.value,
                statement=f"Company domain explicitly registered as {company_domain}",
                source_url=company_domain,
                source_type="CRM_RECORD",
                confidence=0.98,
            )

        # 2. Check metadata
        if metadata_json:
            for k in ["website", "website_url", "domain", "url"]:
                val = metadata_json.get(k)
                if val and isinstance(val, str) and val not in candidates:
                    candidates.append(val)
                    evidence_collector.add_evidence(
                        category=EvidenceCategory.BUSINESS.value,
                        statement=f"Website identified in lead metadata field '{k}': {val}",
                        source_url=val,
                        source_type="LEAD_METADATA",
                        confidence=0.95,
                    )

        # Filter and validate candidates
        valid_urls: List[str] = []
        for cand in candidates:
            try:
                sanitized = validate_and_sanitize_target_url(cand)
                if sanitized not in valid_urls:
                    valid_urls.append(sanitized)
            except SSRFValidationError:
                continue

        if not valid_urls:
            return WebsiteResolution(
                found=False,
                primary_url=None,
                alternatives=[],
                confidence=0.0,
                evidence=evidence_collector.get_all(),
            )

        return WebsiteResolution(
            found=True,
            primary_url=valid_urls[0],
            alternatives=valid_urls[1:],
            confidence=0.95,
            evidence=evidence_collector.get_all(),
        )

    @classmethod
    def discover_internal_pages(
        cls,
        base_url: str,
        found_links: List[str],
        max_pages: int = MAX_PAGES_PER_RESEARCH,
    ) -> List[str]:
        base_domain = urlparse(base_url).netloc.lower()
        prioritized: List[str] = []
        other_internal: List[str] = []

        seen = {base_url.rstrip("/")}

        for link in found_links:
            absolute = urljoin(base_url, link).split("#")[0].split("?")[0].rstrip("/")
            parsed = urlparse(absolute)
            if parsed.netloc.lower() == base_domain and absolute not in seen:
                seen.add(absolute)
                path = parsed.path.lower()
                if any(kw in path for kw in RELEVANT_PATH_KEYWORDS):
                    prioritized.append(absolute)
                else:
                    other_internal.append(absolute)

        # Select up to max_pages - 1 (homepage is page 0)
        selected = (prioritized + other_internal)[: (max_pages - 1)]
        return selected
