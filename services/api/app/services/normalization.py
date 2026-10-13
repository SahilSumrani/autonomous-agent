import re
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# Tracking query parameters to strip
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "igsh", "igshid", "ref", "ref_src", "_hsenc", "_hsmi",
    "mc_cid", "mc_eid"
}

# Platform-owned domains that can never become a company/lead domain
PLATFORM_OWNED_DOMAINS = {
    "linkedin.com",
    "reddit.com",
    "threads.net",
    "threads.com",
    "instagram.com",
    "facebook.com",
    "x.com",
    "twitter.com",
    "google.com",
    "bing.com",
    "duckduckgo.com",
    "youtube.com",
    "tiktok.com",
    "apple.com",
    "linktr.ee",
    "t.co",
}

# Public free webmail and email-provider domains that cannot represent a company website
EMAIL_PROVIDER_DOMAINS = {
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "ymail.com",
    "hotmail.com",
    "outlook.com",
    "live.com",
    "msn.com",
    "icloud.com",
    "me.com",
    "mac.com",
    "protonmail.com",
    "proton.me",
    "mail.com",
    "email.com",
    "aol.com",
    "zoho.com",
    "yandex.com",
    "gmx.com",
    "gmx.net",
    "fastmail.com",
}

# Generic placeholder, template, and test domains
PLACEHOLDER_DOMAINS = {
    "example.com",
    "example.org",
    "example.net",
    "example.edu",
    "test.com",
    "sample.com",
    "placeholder.com",
    "yoursite.com",
    "mysite.com",
    "website.com",
    "domain.com",
    "yourdomain.com",
    "localhost",
}

DISALLOWED_BUSINESS_DOMAINS = PLATFORM_OWNED_DOMAINS | EMAIL_PROVIDER_DOMAINS | PLACEHOLDER_DOMAINS


def is_platform_owned_domain(domain: Optional[str]) -> bool:
    """Check if domain belongs to a known platform/social network."""
    if not domain:
        return False
    d = domain.lower().strip()
    if d.startswith("www."):
        d = d[4:]
    return any(d == pod or d.endswith(f".{pod}") for pod in PLATFORM_OWNED_DOMAINS)


def is_disallowed_business_domain(domain: Optional[str]) -> bool:
    """Check if domain is a platform, public email provider, or placeholder domain."""
    if not domain:
        return True
    d = domain.lower().strip()
    if d.startswith("www."):
        d = d[4:]
    return any(d == bad or d.endswith(f".{bad}") for bad in DISALLOWED_BUSINESS_DOMAINS)


def clean_social_post_text(text: Optional[str], author_hint: Optional[str] = None) -> str:
    """
    Clean extracted social media (Threads, Reddit, etc.) post text by removing
    scraped UI chrome such as Follow buttons, inline audio alerts, and trailing
    Like/Reply/Repost/Share counters.
    """
    if not text:
        return ""
    t = text.strip()

    # 1. Author-specific header strip if author hint provided
    if author_hint:
        h = author_hint.lstrip("@").strip()
        if h:
            t = re.sub(
                rf"^Follow\s*{re.escape(h)}\s*(?:\d{{1,2}}/\d{{1,2}}/\d{{2,4}}|\d+[mhdws]|yesterday|just now)?\s*(?:More)?\s*",
                "",
                t,
                flags=re.IGNORECASE,
            )

    # 2. Generic leading Follow artifact strip
    t = re.sub(
        r"^Follow\s*[a-zA-Z0-9_\.]*?(?:(?:\d{1,2}/\d{1,2}/\d{2,4})|(?:\d+[mhdws])|yesterday|just now)?\s*(?:More)?\s*",
        "",
        t,
        flags=re.IGNORECASE,
    )
    t = re.sub(r"^Follow\s+[a-zA-Z0-9_\.]+\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"^Follow\s*", "", t, flags=re.IGNORECASE)

    # 3. Inline platform tags
    t = re.sub(r"\b(Audio is muted|Audio unavailable|Log in to like|Log in)\b", "", t, flags=re.IGNORECASE)

    # 4. Trailing action buttons (Like, Reply, Repost, Share with optional counts)
    t = re.sub(
        r"(?:\s*[1-9]\d{0,1}/[1-9]\d{0,1}\s*)?(?:\s*(?:Like|Reply|Repost|Share)\s*\d*)+$",
        "",
        t,
        flags=re.IGNORECASE,
    )
    t = re.sub(r"\s*[1-9]\d{0,1}/[1-9]\d{0,1}$", "", t)
    t = re.sub(r"\s*More$", "", t, flags=re.IGNORECASE)

    # Normalize repeated whitespace while preserving newlines
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in t.split("\n")]
    t = "\n".join(line for line in lines if line)
    return t.strip()


# Common legal suffixes for company name normalization
LEGAL_SUFFIXES = [
    r"\binc\.?$", r"\bllc\.?$", r"\bltd\.?$", r"\bcorp\.?$", r"\bcorporation$",
    r"\bgmbh\.?$", r"\bpvt\.?\s*ltd\.?$", r"\bco\.?$", r"\bllp\.?$"
]
LEGAL_SUFFIX_REGEX = re.compile("|".join(LEGAL_SUFFIXES), re.IGNORECASE)


def normalize_domain(url_or_domain: Optional[str]) -> Optional[str]:
    """
    Extract and normalize canonical root/subdomain from URL or raw domain string.
    Examples:
        'https://www.example.com/path?arg=1' -> 'example.com'
        'http://shop.example.com/' -> 'shop.example.com'
        'WWW.EXAMPLE.COM' -> 'example.com'
    """
    if not url_or_domain or not url_or_domain.strip():
        return None

    raw = url_or_domain.strip().lower()

    # Prepend dummy scheme if missing so urllib parses netloc accurately
    if not raw.startswith(("http://", "https://")):
        raw = f"https://{raw}"

    try:
        parsed = urlparse(raw)
        host = parsed.netloc or parsed.path
        # Remove port if present
        host = host.split(":")[0]
        # Remove trailing slash or path components
        host = host.split("/")[0].strip()

        # Remove leading 'www.' while preserving subdomains (e.g., 'app.example.com')
        if host.startswith("www.") and len(host) > 4:
            host = host[4:]

        return host if host else None
    except Exception:
        return None


def normalize_email(email: Optional[str]) -> Optional[str]:
    """
    Normalize email address: strip whitespace and lowercase.
    Preserves exact local-part characters without guessing alias semantics.
    """
    if not email or not email.strip():
        return None

    cleaned = email.strip().lower()
    if "@" not in cleaned or cleaned.startswith("@") or cleaned.endswith("@"):
        return None

    return cleaned


def normalize_company_name(name: Optional[str]) -> Optional[str]:
    """
    Normalize company name for deterministic matching:
    - Lowercase
    - Collapse repeated whitespace
    - Strip common punctuation
    - Strip trailing corporate entity designations (LLC, Inc, Ltd, etc.)
    """
    if not name or not name.strip():
        return None

    cleaned = name.strip().lower()
    # Strip punctuation except alphanumeric and space
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    # Collapse multiple whitespaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Strip legal entity suffixes
    cleaned = LEGAL_SUFFIX_REGEX.sub("", cleaned).strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned if cleaned else None


def normalize_profile_url(url: Optional[str]) -> Optional[str]:
    """
    Normalize social or web profile URLs:
    - Enforce https scheme
    - Lowercase domain
    - Strip tracking query parameters
    - Strip trailing slash
    - Preserve meaningful path segments (e.g. /in/username)
    """
    if not url or not url.strip():
        return None

    raw = url.strip()
    if not raw.startswith(("http://", "https://")):
        raw = f"https://{raw}"

    try:
        parsed = urlparse(raw)
        netloc = parsed.netloc.lower()
        if netloc.startswith("www.") and len(netloc) > 4:
            netloc = netloc[4:]

        path = parsed.path.rstrip("/")

        # Filter out tracking query params
        query_tuples = parse_qsl(parsed.query, keep_blank_values=False)
        filtered_query = [(k, v) for k, v in query_tuples if k.lower() not in TRACKING_PARAMS]
        clean_query = urlencode(filtered_query)

        clean_url = urlunparse((
            "https",
            netloc,
            path,
            "",
            clean_query,
            ""  # Strip fragment
        ))
        return clean_url
    except Exception:
        return None


def normalize_username(username: Optional[str]) -> Optional[str]:
    """
    Normalize handle/username: strip leading '@', strip whitespace, lowercase.
    """
    if not username or not username.strip():
        return None

    cleaned = username.strip().lower()
    while cleaned.startswith("@"):
        cleaned = cleaned[1:]

    return cleaned if cleaned else None


def normalize_phone(phone: Optional[str]) -> Optional[str]:
    """
    Normalize phone numbers into international digits format.
    Example: '+1 (555) 123-4567' -> '+15551234567'
    """
    if not phone or not phone.strip():
        return None

    raw = phone.strip()
    has_plus = raw.startswith("+")
    digits = re.sub(r"\D", "", raw)

    if not digits:
        return None

    return f"+{digits}" if has_plus else digits
