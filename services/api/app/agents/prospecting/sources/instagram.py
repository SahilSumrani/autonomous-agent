import re
from typing import Any, Dict, List, Optional

from packages.shared_types.prospecting import ProspectingSourceType
from services.api.app.agents.prospecting.sources.base import (
    DiscoveredCandidateItem,
    ProspectingSource,
    SecurityChallengeResult,
)
from services.api.app.services.normalization import (
    normalize_domain,
    normalize_profile_url,
    normalize_username,
)

INSTAGRAM_CHALLENGE_PATTERNS = [
    r"log in to continue",
    r"log in to see photos and videos",
    r"checkpoint_required",
    r"challenge_required",
    r"please wait a few minutes before you try again",
    r"help us confirm that you own this account",
    r"we restrict certain activity",
    r"suspected automated behavior",
]


class InstagramSource(ProspectingSource):
    source_type = ProspectingSourceType.INSTAGRAM

    def get_initial_url(self, query: Optional[str]) -> str:
        if not query:
            return "https://www.instagram.com/explore/"
        clean_q = query.strip()
        if clean_q.startswith("http://") or clean_q.startswith("https://"):
            return clean_q
        if clean_q.startswith("#"):
            tag = clean_q.lstrip("#")
            return f"https://www.instagram.com/explore/tags/{tag}/"
        if clean_q.startswith("@"):
            handle = clean_q.lstrip("@")
            return f"https://www.instagram.com/{handle}/"
        return f"https://www.instagram.com/explore/tags/{clean_q}/"

    def detect_security_challenge(self, page_data: Dict[str, Any]) -> SecurityChallengeResult:
        text = page_data.get("visible_text") or ""
        title = page_data.get("page_title") or ""
        url = page_data.get("url") or ""

        common = self.check_common_blockers(text, title)
        if common:
            return common

        combined = f"{url} {title} {text}".lower()
        for pat in INSTAGRAM_CHALLENGE_PATTERNS:
            if re.search(pat, combined, re.IGNORECASE):
                challenge_type = "LOGIN_REQUIRED" if "log in" in pat else "SECURITY_CHECK"
                return SecurityChallengeResult(
                    is_blocked=True,
                    challenge_type=challenge_type,
                    reason=f"Instagram barrier detected: {pat}",
                )

        return SecurityChallengeResult(is_blocked=False)

    def discover_candidates(
        self,
        page_data: Dict[str, Any],
        query: Optional[str] = None,
    ) -> List[DiscoveredCandidateItem]:
        text = page_data.get("visible_text") or ""
        url = page_data.get("url") or ""
        links = page_data.get("links") or []
        title = page_data.get("page_title") or ""

        candidates: List[DiscoveredCandidateItem] = []
        seen_handles = set()

        # 1. Structured posts/items if present in observation
        structured_posts = page_data.get("posts") or page_data.get("content_units") or []
        for post in structured_posts:
            if isinstance(post, dict):
                p_handle = post.get("author") or post.get("handle") or post.get("username")
                p_caption = post.get("caption") or post.get("text") or ""
                p_url = post.get("url") or url
                p_links = post.get("links") or []
                if p_handle:
                    norm_h = normalize_username(p_handle)
                    if norm_h and norm_h not in seen_handles:
                        seen_handles.add(norm_h)
                        # Domain from links or caption
                        domain = None
                        for lk in p_links:
                            dom = normalize_domain(lk)
                            if dom and "instagram.com" not in dom and "facebook.com" not in dom:
                                domain = dom
                                break
                        if not domain:
                            domain_match = re.search(r"\b([a-zA-Z0-9-]+\.(?:com|org|io|co|co\.uk|ai|net|store))\b", p_caption, re.IGNORECASE)
                            if domain_match:
                                domain = normalize_domain(domain_match.group(1))

                        candidates.append(
                            DiscoveredCandidateItem(
                                source_url=p_url,
                                canonical_url=f"https://www.instagram.com/{norm_h}/",
                                platform="INSTAGRAM",
                                username_or_handle=f"@{norm_h}",
                                company_name=norm_h.replace("_", " ").title(),
                                domain=domain,
                                evidence=f"Instagram post by @{norm_h}: {p_caption[:400]}",
                                confidence=0.85,
                                raw_payload={"handle": norm_h, "caption": p_caption, "domain": domain, "url": p_url},
                            )
                        )

        # 2. Check if current page is itself a public profile (e.g. instagram.com/brandname)
        profile_match = re.search(r"instagram\.com/([a-zA-Z0-9_\.]+)/?$", url)
        if profile_match:
            handle = profile_match.group(1)
            if handle not in ("explore", "reels", "direct", "accounts", "p", "tags"):
                norm_handle = normalize_username(handle)
                if norm_handle and norm_handle not in seen_handles:
                    seen_handles.add(norm_handle)
                    # Extract external link if visible in links or text
                    domain = None
                    for link in links:
                        if isinstance(link, str) and not ("instagram.com" in link or "facebook.com" in link):
                            dom = normalize_domain(link)
                            if dom:
                                domain = dom
                                break
                    if not domain:
                        domain_match = re.search(r"\b([a-zA-Z0-9-]+\.(?:com|org|io|co|co\.uk|ai|net|store))\b", text, re.IGNORECASE)
                        if domain_match:
                            domain = normalize_domain(domain_match.group(1))

                    clean_company = title.replace("• Instagram photos and videos", "").replace("• Instagram", "").strip() or norm_handle
                    candidates.append(
                        DiscoveredCandidateItem(
                            source_url=url,
                            canonical_url=f"https://www.instagram.com/{norm_handle}/",
                            platform="INSTAGRAM",
                            username_or_handle=f"@{norm_handle}",
                            company_name=clean_company,
                            domain=domain,
                            evidence=f"Instagram profile: @{norm_handle}. {text[:300]}",
                            confidence=0.8,
                            raw_payload={"url": url, "handle": norm_handle, "domain": domain},
                        )
                    )

        # 3. Extract handles mentioned in links
        for link in links:
            if isinstance(link, str):
                match = re.search(r"instagram\.com/([a-zA-Z0-9_\.]+)/?", link)
                if match:
                    h = match.group(1)
                    if h not in ("explore", "reels", "direct", "accounts", "p", "stories", "tags"):
                        norm_h = normalize_username(h)
                        if norm_h and norm_h not in seen_handles:
                            seen_handles.add(norm_h)
                            candidates.append(
                                DiscoveredCandidateItem(
                                    source_url=link,
                                    canonical_url=f"https://www.instagram.com/{norm_h}/",
                                    platform="INSTAGRAM",
                                    username_or_handle=f"@{norm_h}",
                                    company_name=norm_h.replace("_", " ").title(),
                                    evidence=f"Discovered Instagram handle @{norm_h} on {url}: {text[:200]}",
                                    confidence=0.6,
                                    raw_payload={"url": link, "handle": norm_h},
                                )
                            )

        # 4. Extract text mentions like @handle with surrounding context snippet
        for match in re.finditer(r"@([a-zA-Z0-9_\.]{3,30})", text):
            h = match.group(1)
            norm_h = normalize_username(h)
            if norm_h and norm_h not in seen_handles:
                seen_handles.add(norm_h)
                # Extract snippet around mention (100 chars before, 200 chars after)
                start_idx = max(0, match.start() - 50)
                end_idx = min(len(text), match.end() + 250)
                snippet = text[start_idx:end_idx].strip()
                # Check for domain in snippet
                domain = None
                dom_match = re.search(r"\b([a-zA-Z0-9-]+\.(?:com|org|io|co|co\.uk|ai|net|store))\b", snippet, re.IGNORECASE)
                if dom_match:
                    domain = normalize_domain(dom_match.group(1))

                candidates.append(
                    DiscoveredCandidateItem(
                        source_url=url,
                        canonical_url=f"https://www.instagram.com/{norm_h}/",
                        platform="INSTAGRAM",
                        username_or_handle=f"@{norm_h}",
                        company_name=norm_h.replace("_", " ").title(),
                        domain=domain,
                        evidence=f"Visible post mentioning @{norm_h}: {snippet}",
                        confidence=0.7,
                        raw_payload={"mention": norm_h, "snippet": snippet},
                    )
                )

        return candidates

    def build_dedup_key(self, candidate: DiscoveredCandidateItem) -> str:
        handle = candidate.username_or_handle or ""
        norm_h = normalize_username(handle) or handle.strip().lower().lstrip("@")
        if norm_h:
            return f"instagram:{norm_h}"
        if candidate.domain:
            return f"domain:{candidate.domain}"
        return f"url:{candidate.source_url}"

    def next_urls(self, page_data: Dict[str, Any], query: Optional[str] = None) -> List[str]:
        urls: List[str] = []
        seen = set()

        structured = page_data.get("posts") or page_data.get("content_units") or []
        for item in structured:
            if isinstance(item, dict):
                p_url = item.get("url")
                if p_url and "instagram.com" in p_url and ("/p/" in p_url or "/reel/" in p_url) and p_url not in seen:
                    seen.add(p_url)
                    urls.append(p_url)

        for link in page_data.get("links") or []:
            if not isinstance(link, str):
                continue
            clean = link.split("?")[0].split("#")[0]
            if "instagram.com" in clean and ("/p/" in clean or "/reel/" in clean) and clean not in seen:
                seen.add(clean)
                urls.append(clean)
            elif "instagram.com" in clean and re.search(r"instagram\.com/[a-zA-Z0-9._]+/?$", clean) and clean not in seen:
                if not any(skip in clean for skip in ["/explore", "/direct", "/stories", "/accounts", "/developer", "/about", "/legal"]):
                    seen.add(clean)
                    urls.append(clean)

        return urls
