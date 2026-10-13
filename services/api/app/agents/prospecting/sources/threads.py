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
    clean_social_post_text,
    is_disallowed_business_domain,
    normalize_domain,
    normalize_username,
)

THREADS_CHALLENGE_PATTERNS = [
    r"log in with instagram",
    r"log in to continue",
    r"log in to view",
    r"challenge_required",
    r"checkpoint_required",
    r"please slow down",
    r"confirm that you own this account",
    r"verify you are a human",
    r"verify you are human",
    r"solve the captcha",
    r"captcha challenge",
    r"security check",
]


DEFAULT_THREADS_BUYER_KEYWORDS = [
    "looking for a developer",
    "need a developer",
    "looking for web developer",
    "need a website",
    "recommend someone to build",
    "looking for app developer",
    "looking for designer",
    "need someone to build",
    "who can build an app",
    "looking to hire developer",
]


class ThreadsSource(ProspectingSource):
    source_type = ProspectingSourceType.THREADS

    def get_initial_url(self, query: Optional[str]) -> str:
        if not query:
            return "https://www.threads.com/"
        clean_q = query.strip()
        if clean_q.startswith("http://") or clean_q.startswith("https://"):
            return clean_q
        if clean_q.startswith("@"):
            handle = clean_q.lstrip("@")
            return f"https://www.threads.net/@{handle}"
        encoded = clean_q.replace(" ", "%20")
        return f"https://www.threads.com/search?q={encoded}&filter=recent"

    def get_entry_urls(self, query: Optional[str] = None, profile: Optional[Any] = None) -> List[str]:
        if query and query.strip():
            return [self.get_initial_url(query)]
        urls = ["https://www.threads.com/"]
        raw_keywords = []
        if profile and hasattr(profile, "ideal_customer_keywords") and profile.ideal_customer_keywords:
            raw_keywords = profile.ideal_customer_keywords

        # Filter out generic agency marketing terms that attract competitors instead of clients
        filtered_keywords = [
            kw for kw in raw_keywords
            if not any(bad in kw.lower() for bad in ["redesign", "workflow", "build mvp"])
        ]

        keywords = filtered_keywords if filtered_keywords else DEFAULT_THREADS_BUYER_KEYWORDS

        for kw in keywords:
            encoded = kw.strip().replace(" ", "%20")
            if encoded:
                urls.append(f"https://www.threads.com/search?q={encoded}&filter=recent")
        return urls

    def detect_security_challenge(self, page_data: Dict[str, Any]) -> SecurityChallengeResult:
        text = page_data.get("visible_text") or ""
        title = page_data.get("page_title") or ""
        url = page_data.get("url") or ""

        common = self.check_common_blockers(text, title)
        if common:
            return common

        combined = f"{url} {title} {text}".lower()
        for pat in THREADS_CHALLENGE_PATTERNS:
            if re.search(pat, combined, re.IGNORECASE):
                return SecurityChallengeResult(
                    is_blocked=True,
                    challenge_type="LOGIN_REQUIRED" if "log in" in pat else "SECURITY_CHECK",
                    reason=f"Threads security challenge detected: {pat}",
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

        candidates: List[DiscoveredCandidateItem] = []
        seen_handles = set()

        # 1. Structured posts/content units in observation (grounded strictly in the actual post author)
        structured_posts = page_data.get("posts") or page_data.get("content_units") or page_data.get("contentUnits") or []
        for post in structured_posts:
            if isinstance(post, dict):
                p_handle = post.get("author") or post.get("handle") or post.get("username")
                raw_text = post.get("text") or post.get("body") or post.get("content") or ""
                p_url = post.get("url") or url
                p_links = post.get("links") or []

                if not p_handle or len(raw_text.strip()) < 15:
                    continue

                norm_h = normalize_username(p_handle)
                if not norm_h or norm_h in seen_handles:
                    continue

                # Clean UI artifacts (Follow headers, audio alerts, Like/Reply/Repost/Share counters)
                p_text = clean_social_post_text(raw_text, norm_h)
                if len(p_text) < 15:
                    continue

                # Require connection between the actual author and buying intent / business signals
                signals = SignalDetectionEngine.analyze(text=p_text, source_url=p_url)
                is_false_pos = SignalDetectionEngine.check_false_positive(p_text)
                if is_false_pos:
                    continue

                # Must have commercial signal or explicit buying intent to qualify as a candidate
                has_intent = SignalDetectionEngine.has_explicit_intent(signals)
                if not signals and not has_intent:
                    continue

                seen_handles.add(norm_h)

                # Domain from links or author's post text (reject platform, email, and placeholder domains)
                domain = None
                for lk in p_links:
                    dom = normalize_domain(lk)
                    if dom and not is_disallowed_business_domain(dom):
                        domain = dom
                        break
                if not domain:
                    domain_match = re.search(
                        r"\b([a-zA-Z0-9-]+\.(?:com|org|io|co|co\.uk|ai|net|store))\b",
                        p_text,
                        re.IGNORECASE,
                    )
                    if domain_match:
                        cand_dom = normalize_domain(domain_match.group(1))
                        if cand_dom and not is_disallowed_business_domain(cand_dom):
                            domain = cand_dom

                domain_host = "threads.net" if "threads.net" in (p_url or url) else "threads.com"
                evidence = f"Observed Threads post by @{norm_h}: \"{p_text[:350]}\""
                primary_signal = signals[0] if signals else None
                candidates.append(
                    DiscoveredCandidateItem(
                        source_url=p_url,
                        canonical_url=f"https://www.{domain_host}/@{norm_h}",
                        platform="THREADS",
                        username_or_handle=f"@{norm_h}",
                        company_name=norm_h.replace("_", " ").title(),
                        domain=domain,
                        evidence=evidence,
                        confidence=primary_signal.confidence if primary_signal else 0.85,
                        raw_payload={
                            "handle": norm_h,
                            "text": p_text,
                            "domain": domain,
                            "url": p_url,
                            "signal": primary_signal.signal_type.value if primary_signal else None,
                        },
                    )
                )

        # 1b. Fallback: Parse visible text blocks directly if structured elements were omitted or minimized
        if len(candidates) == 0 and text:
            pattern = re.compile(
                r"(?:^|\n)([a-zA-Z0-9_\.]{3,30})\s*(?:>\s*[^0-9\n]+\s*)?(\d+[mhdws]|yesterday|just now)\n+([\s\S]+?)(?=\n+[a-zA-Z0-9_\.]{3,30}(?:\s*>\s*[^0-9\n]+\s*)?\s+(?:\d+[mhdws]|yesterday|just now)|\Z)",
                re.IGNORECASE,
            )
            for m in pattern.finditer(text):
                raw_handle = m.group(1).strip()
                tstamp = m.group(2).strip()
                raw_p_text = m.group(3).strip()

                norm_h = normalize_username(raw_handle)
                if not norm_h or norm_h in seen_handles or len(raw_p_text) < 15:
                    continue

                p_text = clean_social_post_text(raw_p_text, norm_h)
                if len(p_text) < 15:
                    continue

                signals = SignalDetectionEngine.analyze(text=p_text, source_url=url)
                if SignalDetectionEngine.check_false_positive(p_text):
                    continue

                has_intent = SignalDetectionEngine.has_explicit_intent(signals)
                if not signals and not has_intent:
                    continue

                seen_handles.add(norm_h)
                primary_signal = signals[0] if signals else None
                evidence = f"Observed Threads post by @{norm_h} ({tstamp}): \"{p_text[:350]}\""
                candidates.append(
                    DiscoveredCandidateItem(
                        source_url=url,
                        canonical_url=f"https://www.threads.com/@{norm_h}",
                        platform="THREADS",
                        username_or_handle=f"@{norm_h}",
                        company_name=norm_h.replace("_", " ").title(),
                        domain=None,
                        evidence=evidence,
                        confidence=primary_signal.confidence if primary_signal else 0.85,
                        raw_payload={
                            "handle": norm_h,
                            "text": p_text,
                            "timestamp": tstamp,
                            "url": url,
                            "signal": primary_signal.signal_type.value if primary_signal else None,
                        },
                    )
                )

        # 2. Check if current page is an active Threads profile page
        profile_match = re.search(r"threads\.(?:net|com)/@([a-zA-Z0-9_\.]+)/?$", url)
        if profile_match:
            handle = profile_match.group(1)
            norm_h = normalize_username(handle)
            if norm_h and norm_h not in seen_handles:
                # Check signals on profile page text
                clean_bio_text = clean_social_post_text(text, norm_h)
                signals = SignalDetectionEngine.analyze(text=clean_bio_text, source_url=url)
                if signals and not SignalDetectionEngine.check_false_positive(clean_bio_text):
                    seen_handles.add(norm_h)
                    domain = None
                    for link in links:
                        if isinstance(link, str):
                            dom = normalize_domain(link)
                            if dom and not is_disallowed_business_domain(dom):
                                domain = dom
                                break
                    if not domain:
                        domain_match = re.search(
                            r"\b([a-zA-Z0-9-]+\.(?:com|org|io|co|co\.uk|ai|net|store))\b",
                            clean_bio_text,
                            re.IGNORECASE,
                        )
                        if domain_match:
                            cand_dom = normalize_domain(domain_match.group(1))
                            if cand_dom and not is_disallowed_business_domain(cand_dom):
                                domain = cand_dom

                    primary = signals[0]
                    candidates.append(
                        DiscoveredCandidateItem(
                            source_url=url,
                            canonical_url=f"https://www.threads.com/@{norm_h}",
                            platform="THREADS",
                            username_or_handle=f"@{norm_h}",
                            company_name=norm_h.replace("_", " ").title(),
                            domain=domain,
                            evidence=f"Threads profile @{norm_h} demonstrates intent: {primary.evidence}",
                            confidence=primary.confidence,
                            raw_payload={"handle": norm_h, "url": url, "domain": domain, "signal": primary.signal_type.value},
                        )
                    )

        # Note: Arbitrary in-text @mentions (where a user mentions someone else in their post)
        # are explicitly rejected to prevent attributing another author's posts to third-party handles.

        return candidates

    def build_dedup_key(self, candidate: DiscoveredCandidateItem) -> str:
        handle = candidate.username_or_handle or ""
        norm_h = normalize_username(handle) or handle.strip().lower().lstrip("@")
        if norm_h:
            return f"threads:{norm_h}"
        return f"url:{candidate.source_url}"

    def next_urls(self, page_data: Dict[str, Any], query: Optional[str] = None) -> List[str]:
        urls: List[str] = []
        seen = set()

        structured = page_data.get("posts") or page_data.get("content_units") or []
        for item in structured:
            if isinstance(item, dict):
                p_url = item.get("url")
                if p_url and "threads." in p_url and ("/post/" in p_url or "/t/" in p_url) and p_url not in seen:
                    seen.add(p_url)
                    urls.append(p_url)

        for link in page_data.get("links") or []:
            if not isinstance(link, str):
                continue
            clean = link.split("?")[0].split("#")[0]
            if "threads." in clean and ("/post/" in clean or "/t/" in clean) and clean not in seen:
                seen.add(clean)
                urls.append(clean)
            elif "threads." in clean and re.search(r"threads\.(?:net|com)/@[a-zA-Z0-9._]+/?$", clean) and clean not in seen:
                seen.add(clean)
                urls.append(clean)

        return urls
