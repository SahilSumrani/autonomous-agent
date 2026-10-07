import re
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# Tracking query parameters to strip
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "igsh", "igshid", "ref", "ref_src", "_hsenc", "_hsmi",
    "mc_cid", "mc_eid"
}

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
