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
    normalize_domain,
    normalize_username,
)

REDDIT_CHALLENGE_PATTERNS = [
    r"whoa there, to continue, verify you are a human",
    r"verify you are (?:a )?human",
    r"you've been blocked by network security",
    r"you have been blocked",
    r"request blocked by security rules",
    r"please solve the captcha",
    r"solve the captcha",
    r"captcha challenge",
    r"security check",
]


class RedditSource(ProspectingSource):
    source_type = ProspectingSourceType.REDDIT

    def get_initial_url(self, query: Optional[str]) -> str:
        if not query:
            return "https://www.reddit.com/r/smallbusiness/"
        clean_q = query.strip()
        if clean_q.startswith("http://") or clean_q.startswith("https://"):
            return clean_q
        if clean_q.startswith("r/"):
            return f"https://www.reddit.com/{clean_q}/"
        # Search query across subreddits
        encoded = clean_q.replace(" ", "%20")
        return f"https://www.reddit.com/search/?q={encoded}"

    def get_entry_urls(self, query: Optional[str] = None, profile: Optional[Any] = None) -> List[str]:
        if query and query.strip():
            return [self.get_initial_url(query)]
        urls = [
            "https://www.reddit.com/r/forhire/",
            "https://www.reddit.com/r/smallbusiness/",
            "https://www.reddit.com/r/startups/",
        ]
        keywords = []
        if profile and hasattr(profile, "ideal_customer_keywords") and profile.ideal_customer_keywords:
            keywords = profile.ideal_customer_keywords
        else:
            keywords = ["need a website", "looking for developer", "build MVP"]

        for kw in keywords:
            encoded = kw.strip().replace(" ", "%20")
            if encoded:
                urls.append(f"https://www.reddit.com/search/?q={encoded}")
        return urls

    def detect_security_challenge(self, page_data: Dict[str, Any]) -> SecurityChallengeResult:
        text = page_data.get("visible_text") or ""
        title = page_data.get("page_title") or ""
        url = page_data.get("url") or ""

        common = self.check_common_blockers(text, title)
        if common:
            return common

        combined = f"{url} {title} {text}".lower()
        for pat in REDDIT_CHALLENGE_PATTERNS:
            if re.search(pat, combined, re.IGNORECASE):
                return SecurityChallengeResult(
                    is_blocked=True,
                    challenge_type="CAPTCHA" if "captcha" in pat or "human" in pat else "BLOCKED_IP",
                    reason=f"Reddit security challenge detected: {pat}",
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
        seen_posts = set()

        # 1. Structured posts/content units in observation
        structured_posts = page_data.get("posts") or page_data.get("content_units") or page_data.get("contentUnits") or []
        for post in structured_posts:
            if isinstance(post, dict):
                p_author = post.get("author") or post.get("username")
                p_title = post.get("title") or ""
                p_body = post.get("body") or post.get("text") or post.get("selftext") or ""
                p_url = post.get("url") or url
                p_sub = post.get("subreddit") or "reddit"
                p_links = post.get("links") or []

                combined_post = f"{p_title} {p_body}".strip()
                if not combined_post:
                    continue

                norm_author = normalize_username(p_author) if p_author else None
                post_id = post.get("postId") or post.get("post_id") or post.get("id")
                if not post_id:
                    post_id_match = re.search(r"/comments/([a-zA-Z0-9_]+)", p_url)
                    post_id = post_id_match.group(1) if post_id_match else None
                dedup_id = f"post:{post_id}" if post_id else (f"post_url:{p_url}" if p_url != url else f"author_title:{norm_author}:{p_title[:40]}")
                if dedup_id in seen_posts:
                    continue
                seen_posts.add(dedup_id)

                # Domain from links or post body
                domain = None
                for lk in p_links:
                    dom = normalize_domain(lk)
                    if dom and "reddit.com" not in dom:
                        domain = dom
                        break
                if not domain:
                    domain_match = re.search(r"\b([a-zA-Z0-9-]+\.(?:com|org|io|co|co\.uk|ai|net|store))\b", combined_post, re.IGNORECASE)
                    if domain_match:
                        domain = normalize_domain(domain_match.group(1))

                cand_name = f"u/{norm_author}" if norm_author else f"r/{p_sub}: {p_title[:40]}"
                evidence = f"Reddit post in r/{p_sub} by u/{norm_author or 'anonymous'}: '{p_title}'. {p_body[:300]}"
                candidates.append(
                    DiscoveredCandidateItem(
                        source_url=p_url,
                        canonical_url=p_url,
                        platform="REDDIT",
                        username_or_handle=f"u/{norm_author}" if norm_author else None,
                        company_name=cand_name,
                        domain=domain,
                        evidence=evidence.strip(),
                        confidence=0.85,
                        raw_payload={"subreddit": p_sub, "author": norm_author, "post_id": post_id, "title": p_title, "body": p_body, "domain": domain},
                    )
                )

        # 2. Check if current page is a specific Reddit post/thread
        post_match = re.search(r"reddit\.com/r/([^/]+)/comments/([a-zA-Z0-9]+)/?([^/]*)", url)
        if post_match:
            subreddit = post_match.group(1)
            post_id = post_match.group(2)
            dedup_id = f"post:{post_id}"
            if dedup_id not in seen_posts:
                seen_posts.add(dedup_id)
                # Find author in text (e.g. "Posted by u/username" or "u/username")
                author_match = re.search(r"\b(?:posted by\s+)?u/([a-zA-Z0-9_\-]+)\b", text, re.IGNORECASE)
                author = author_match.group(1) if author_match else None
                norm_author = normalize_username(author) if author else None

                # Detect signals in the post body
                signals = SignalDetectionEngine.analyze(text=text, source_url=url)
                if signals and not SignalDetectionEngine.check_false_positive(text):
                    primary = signals[0]
                    cand_name = f"u/{norm_author}" if norm_author else f"r/{subreddit} Post"
                    # Check for domain
                    domain = None
                    domain_match = re.search(r"\b([a-zA-Z0-9-]+\.(?:com|org|io|co|co\.uk|ai|net|store))\b", text, re.IGNORECASE)
                    if domain_match and "reddit.com" not in domain_match.group(1):
                        domain = normalize_domain(domain_match.group(1))

                    candidates.append(
                        DiscoveredCandidateItem(
                            source_url=url,
                            canonical_url=url,
                            platform="REDDIT",
                            username_or_handle=f"u/{norm_author}" if norm_author else None,
                            company_name=cand_name,
                            domain=domain,
                            evidence=f"Reddit post in r/{subreddit} with signal: {primary.evidence}",
                            confidence=primary.confidence,
                            raw_payload={"subreddit": subreddit, "author": norm_author, "post_id": post_id, "signal": primary.signal_type.value},
                        )
                    )

        # 3. Discover Reddit posts from search / subreddit listing links
        for link in links:
            if isinstance(link, str) and "/comments/" in link:
                match = re.search(r"reddit\.com/r/([^/]+)/comments/([a-zA-Z0-9]+)/?([^/]*)", link)
                if match:
                    sub = match.group(1)
                    post_id = match.group(2)
                    slug = match.group(3).replace("_", " ")
                    clean_slug = re.sub(r"[^a-zA-Z0-9\s]", "", slug).strip()
                    dedup_id = f"post:{post_id}"
                    if dedup_id not in seen_posts:
                        seen_posts.add(dedup_id)
                        candidates.append(
                            DiscoveredCandidateItem(
                                source_url=link,
                                canonical_url=link,
                                platform="REDDIT",
                                company_name=f"r/{sub}: {clean_slug[:50]}" if clean_slug else f"r/{sub} post",
                                evidence=f"Found Reddit post link in r/{sub}: {slug}",
                                confidence=0.6,
                                raw_payload={"subreddit": sub, "post_id": post_id, "slug": slug},
                            )
                        )

        return candidates

    def build_dedup_key(self, candidate: DiscoveredCandidateItem) -> str:
        # Platform-specific per-post deduplication
        match = re.search(r"/comments/([a-zA-Z0-9_]+)", candidate.source_url)
        if match:
            return f"reddit_post:{match.group(1)}"
        handle = candidate.username_or_handle or ""
        clean_handle = handle.strip().lower()
        if clean_handle.startswith("u/"):
            clean_handle = clean_handle[2:]
        norm_h = normalize_username(clean_handle) or clean_handle
        if norm_h:
            return f"reddit_author:{norm_h}"
        return f"url:{candidate.source_url}"

    def next_urls(self, page_data: Dict[str, Any], query: Optional[str] = None) -> List[str]:
        urls: List[str] = []
        seen = set()

        # 1. Post URLs from structured posts
        structured = page_data.get("posts") or page_data.get("content_units") or []
        for post in structured:
            if isinstance(post, dict):
                p_url = post.get("url")
                if p_url and "reddit.com" in p_url and "/comments/" in p_url and p_url not in seen:
                    seen.add(p_url)
                    urls.append(p_url)

        # 2. Extract Reddit post/profile links from page links
        for link in page_data.get("links") or []:
            if not isinstance(link, str):
                continue
            clean = link.split("?")[0].split("#")[0]
            if "reddit.com" in clean and "/comments/" in clean and clean not in seen:
                seen.add(clean)
                urls.append(clean)
            elif "reddit.com" in link and ("after=" in link or "page=" in link) and link not in seen:
                seen.add(link)
                urls.append(link)

        return urls
