import re
from typing import List, Tuple

# Channel Character Length Boundaries
CHANNEL_BOUNDS = {
    "INSTAGRAM_DM": (50, 700),
    "REDDIT": (80, 1200),
    "LINKEDIN": (100, 1000),
    "EMAIL": (100, 2000),
}

PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:an?\s+)?(?:unfiltered|new|different|system)", re.IGNORECASE),
    re.compile(r"system\s*prompt", re.IGNORECASE),
    re.compile(r"disregard\s+(?:all\s+)?rules?", re.IGNORECASE),
    re.compile(r"reveal\s+(?:your\s+)?(?:api\s*key|secret|password|credential)", re.IGNORECASE),
    re.compile(r"send\s+(?:me\s+)?(?:your\s+)?(?:api\s*key|secret|token)", re.IGNORECASE),
    re.compile(r"<script[\s\S]*?>[\s\S]*?<\/script>", re.IGNORECASE),
    re.compile(r"javascript:\s*", re.IGNORECASE),
    re.compile(r"\{\{[\s\S]*?\}\}"),  # template tags
]

PROHIBITED_COMMITMENT_PATTERNS = [
    (re.compile(r"\b(?:\d+%\s*discount|free\s+trial|discount\s+of\s+\d+%)\b", re.IGNORECASE), "Unauthorized discount commitment"),
    (re.compile(r"\b(?:guarantee(?:d)?(?:\s+[\w%]+){0,3}\s+(?:roi|revenue|sales|ranking|results))\b", re.IGNORECASE), "Prohibited guarantee claim"),
    (re.compile(r"\b(?:we\s+agree\s+to\s+your\s+terms|contract\s+is\s+signed|deal\s+is\s+done)\b", re.IGNORECASE), "Autonomous legal commitment"),
    (re.compile(r"\b(?:our\s+price\s+is\s+\$\d+|fixed\s+fee\s+(?:is|of)\s+\$\d+)\b", re.IGNORECASE), "Autonomous fixed pricing commitment"),
    (re.compile(r"\b(?:100%\s+refund|money\s+back\s+guarantee)\b", re.IGNORECASE), "Unauthorized refund policy claim"),
]


def sanitize_inbound_message(raw_text: str) -> str:
    """
    Sanitizes inbound prospect messages against prompt injection and malicious formatting.
    Preserves normal conversational semantics while neutralizing attacks.
    """
    if not raw_text:
        return ""

    sanitized = raw_text.strip()

    # Neutralize prompt injection phrases by defanging them
    for pattern in PROMPT_INJECTION_PATTERNS:
        sanitized = pattern.sub("[FILTERED_INPUT]", sanitized)

    # Neutralize HTML/XML tags
    sanitized = re.sub(r"<[^>]+>", " ", sanitized)

    # Collapse excessive whitespace
    sanitized = re.sub(r"\s+", " ", sanitized).strip()

    # Cap message length to 4000 characters
    if len(sanitized) > 4000:
        sanitized = sanitized[:4000]

    return sanitized


def validate_reply_length(text: str, channel: str) -> Tuple[bool, str]:
    """
    Validates that a generated reply draft adheres to strict channel character constraints.
    """
    ch_upper = channel.upper()
    min_len, max_len = CHANNEL_BOUNDS.get(ch_upper, (50, 1000))

    length = len(text.strip())
    if length < min_len:
        return False, f"Reply length {length} is below minimum {min_len} for {channel}"
    if length > max_len:
        return False, f"Reply length {length} exceeds maximum {max_len} for {channel}"
    return True, "Valid length"


def detect_prohibited_commitments(text: str) -> List[str]:
    """
    Scans a reply draft for prohibited autonomous commitments (pricing, discounts, guarantees, contracts).
    """
    flags: List[str] = []
    for pattern, description in PROHIBITED_COMMITMENT_PATTERNS:
        if pattern.search(text):
            flags.append(description)
    return flags
