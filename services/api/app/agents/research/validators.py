import ipaddress
import re
import socket
from urllib.parse import urlparse
from typing import Optional, Tuple


# Regex patterns matching prompt injection attempts
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions?", re.IGNORECASE),
    re.compile(r"(reveal|send|print|show)\s+(the\s+)?(system\s+prompt|api\s+key|token|password)", re.IGNORECASE),
    re.compile(r"call\s+this\s+tool", re.IGNORECASE),
    re.compile(r"bypass\s+(approval|permissions?|authentication)", re.IGNORECASE),
    re.compile(r"disregard\s+(the\s+)?rules", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+in\s+dan\s+mode", re.IGNORECASE),
]

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


class SSRFValidationError(ValueError):
    """Raised when a URL targets a prohibited private or local network address."""
    pass


class PromptInjectionDetected(ValueError):
    """Raised or flagged when input content contains overt prompt injection strings."""
    pass


def validate_and_sanitize_target_url(raw_url: str) -> str:
    """
    Validates that a URL is a legitimate public HTTP/HTTPS URL and prevents SSRF attacks.
    Throws SSRFValidationError if the host resolves to a private or loopback IP.
    """
    if not raw_url:
        raise SSRFValidationError("URL cannot be empty")

    url = raw_url.strip()
    if "://" in url:
        scheme = url.split("://", 1)[0].lower()
        if scheme not in ("http", "https"):
            raise SSRFValidationError(f"Invalid URL scheme: {scheme}")
    elif not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise SSRFValidationError(f"Invalid URL scheme: {parsed.scheme}")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFValidationError("Missing hostname in URL")

    # Disallow localhost directly
    if hostname.lower() in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        raise SSRFValidationError(f"Prohibited local hostname: {hostname}")

    # Check for IP address literals
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        ip = None

    if ip is not None:
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise SSRFValidationError(f"Access to private IP range {ip} is blocked")
    else:
        # Not a raw IP literal; validate domain format
        if not re.match(r"^[a-zA-Z0-9.\-]+$", hostname):
            raise SSRFValidationError(f"Invalid characters in hostname: {hostname}")

        # Cloud metadata domains and special local names
        lower_host = hostname.lower()
        if lower_host in ("metadata.google.internal", "instance-data", "metadata", "local", "internal"):
            raise SSRFValidationError(f"Access to cloud metadata host '{hostname}' is blocked")

        # Robust DNS address resolution check: resolve hostname and verify resolved IPs
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            for family, socktype, proto, canonname, sockaddr in addr_info:
                resolved_ip_str = sockaddr[0]
                resolved_ip = ipaddress.ip_address(resolved_ip_str)
                if (
                    resolved_ip.is_private
                    or resolved_ip.is_loopback
                    or resolved_ip.is_link_local
                    or resolved_ip.is_reserved
                    or resolved_ip.is_multicast
                ):
                    raise SSRFValidationError(
                        f"Hostname '{hostname}' resolves to prohibited private address {resolved_ip}"
                    )
                # Explicit check for cloud metadata IP 169.254.169.254
                if str(resolved_ip) == "169.254.169.254":
                    raise SSRFValidationError(f"Hostname '{hostname}' resolves to cloud metadata IP")
        except socket.gaierror:
            # If domain cannot be resolved by DNS (e.g. offline unit testing), block suspicious local/internal domains
            if any(keyword in lower_host for keyword in ("localhost", "internal", "localdomain", "corp")):
                raise SSRFValidationError(f"Unresolvable local or internal host '{hostname}' is blocked")

    return url


def sanitize_untrusted_page_content(text: Optional[str], max_length: int = 10000) -> str:
    """
    Neutralizes prompt injections in untrusted page content.
    Replaces directive patterns with sanitized markers while preserving factual text.
    """
    if not text:
        return ""

    sanitized = text[:max_length]
    for pattern in _INJECTION_PATTERNS:
        sanitized = pattern.sub("[FILTERED_PROMPT_INJECTION_DIRECTIVE]", sanitized)

    return sanitized


def check_prompt_injection(text: str) -> Tuple[bool, Optional[str]]:
    """
    Checks if text contains prompt injection attempts without altering it.
    Returns (is_injected, matched_pattern).
    """
    if not text:
        return False, None

    for pattern in _INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return True, match.group(0)

    return False, None
