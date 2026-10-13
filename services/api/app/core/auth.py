import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Any, Dict, Optional, Tuple
from fastapi import HTTPException, status
from pydantic import BaseModel

from packages.config.settings import settings

DEFAULT_DEV_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class AuthenticationError(HTTPException):
    def __init__(self, detail: str = "Invalid authentication credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class AuthorizationError(HTTPException):
    def __init__(self, detail: str = "Unauthorized tenant access"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class AuthenticatedActor(BaseModel):
    """Authenticated caller identity bound strictly to tenant context."""
    actor_id: str
    organization_id: uuid.UUID
    actor_type: str = "USER"  # "USER", "SYSTEM", "API_KEY", "BROWSER_SESSION"
    session_id: Optional[uuid.UUID] = None
    is_authenticated: bool = True


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64decode(s: str) -> bytes:
    padding = 4 - (len(s) % 4)
    if padding < 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s.encode("utf-8"))


def create_access_token(
    actor_id: Optional[str] = None,
    organization_id: Optional[uuid.UUID] = None,
    role: str = "USER",
    expires_in_seconds: int = 86400,
    *,
    org_id: Optional[uuid.UUID] = None,
    user_id: Optional[str] = None,
) -> str:
    """Generate a cryptographically signed HMAC-SHA256 JWT token bound to actor and organization."""
    actual_org_id = organization_id or org_id
    if not actual_org_id:
        raise ValueError("organization_id is required for create_access_token")
    actual_actor_id = actor_id or user_id or "authenticated_user"

    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": actual_actor_id,
        "org_id": str(actual_org_id),
        "role": role,
        "iat": now,
        "exp": now + expires_in_seconds,
    }
    h_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    p_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signing_input = f"{_b64encode(h_bytes)}.{_b64encode(p_bytes)}".encode("utf-8")
    secret = settings.SECRET_KEY.encode("utf-8")
    signature = hmac.new(secret, signing_input, hashlib.sha256).digest()
    return f"{signing_input.decode('utf-8')}.{_b64encode(signature)}"


def verify_access_token(token: str) -> Dict[str, Any]:
    """Verify cryptographic signature and expiration of an access token."""
    if token.startswith("tv_sess_"):
        raise AuthenticationError("Browser session token cannot be used as user access token. Use browser session authorization.")
    if token.startswith("tv_key_"):
        raise AuthenticationError("API key cannot be used as user access token.")

    parts = token.split(".")
    if len(parts) != 3:
        raise AuthenticationError("Malformed access token structure")

    h_b64, p_b64, s_b64 = parts
    signing_input = f"{h_b64}.{p_b64}".encode("utf-8")
    secret = settings.SECRET_KEY.encode("utf-8")
    expected_sig = hmac.new(secret, signing_input, hashlib.sha256).digest()

    try:
        actual_sig = _b64decode(s_b64)
    except Exception:
        raise AuthenticationError("Invalid token signature encoding")

    if not hmac.compare_digest(expected_sig, actual_sig):
        raise AuthenticationError("Invalid token signature")

    try:
        payload_bytes = _b64decode(p_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        raise AuthenticationError("Corrupt token payload")

    exp = payload.get("exp")
    if exp is not None and time.time() > exp:
        raise AuthenticationError("Access token has expired")

    org_id = payload.get("org_id")
    if not org_id:
        raise AuthenticationError("Token is not bound to an organization identity")

    return payload


def create_api_key(organization_id: uuid.UUID, name: str = "default") -> str:
    """Create a structured, signed API key bound to an organization."""
    org_hex = organization_id.hex
    salt = uuid.uuid4().hex[:12]
    content = f"tv_key_{org_hex}_{salt}"
    secret = settings.SECRET_KEY.encode("utf-8")
    sig = hmac.new(secret, content.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
    return f"{content}_{sig}"


def verify_api_key(api_key: str) -> uuid.UUID:
    """Verify structured API key signature and return bound organization UUID."""
    if not api_key.startswith("tv_key_"):
        raise AuthenticationError("Invalid API key format")
    parts = api_key.split("_")
    # Format: tv_key_<org_hex>_<salt>_<sig>
    if len(parts) != 5:
        raise AuthenticationError("Malformed API key structure")
    org_hex, salt, sig = parts[2], parts[3], parts[4]
    content = f"tv_key_{org_hex}_{salt}"
    secret = settings.SECRET_KEY.encode("utf-8")
    expected_sig = hmac.new(secret, content.encode("utf-8"), hashlib.sha256).hexdigest()[:16]

    if not hmac.compare_digest(expected_sig, sig):
        raise AuthenticationError("Invalid API key signature")

    try:
        return uuid.UUID(hex=org_hex)
    except Exception:
        raise AuthenticationError("Invalid organization in API key")


def create_browser_session_token(
    session_id: uuid.UUID,
    org_id: uuid.UUID,
    user_id: Optional[uuid.UUID] = None,
    browser_id: str = "",
    client_version: str = "2.0.0",
    expires_in_seconds: int = 86400 * 7,
) -> str:
    """Create a persistent cryptographically signed browser session token that survives server restarts."""
    now = int(time.time())
    header = {"alg": "HS256", "typ": "TV_SESS"}
    payload = {
        "session_id": str(session_id),
        "org_id": str(org_id),
        "user_id": str(user_id) if user_id else None,
        "browser_id": browser_id,
        "client_version": client_version,
        "iat": now,
        "exp": now + expires_in_seconds,
    }
    h_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    p_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signing_input = f"{_b64encode(h_bytes)}.{_b64encode(p_bytes)}".encode("utf-8")
    secret = settings.SECRET_KEY.encode("utf-8")
    signature = hmac.new(secret, signing_input, hashlib.sha256).digest()
    return f"tv_sess_{signing_input.decode('utf-8')}.{_b64encode(signature)}"


def verify_browser_session_token(token: str) -> Dict[str, Any]:
    """Verify cryptographic signature and return bound browser session data."""
    if not token.startswith("tv_sess_"):
        raise AuthenticationError("Invalid browser session token format")
    raw = token[8:]
    parts = raw.split(".")
    if len(parts) != 3:
        raise AuthenticationError("Malformed browser session token structure")
    h_b64, p_b64, s_b64 = parts
    signing_input = f"{h_b64}.{p_b64}".encode("utf-8")
    secret = settings.SECRET_KEY.encode("utf-8")
    expected_sig = hmac.new(secret, signing_input, hashlib.sha256).digest()
    try:
        actual_sig = _b64decode(s_b64)
    except Exception:
        raise AuthenticationError("Invalid token signature encoding")
    if not hmac.compare_digest(expected_sig, actual_sig):
        raise AuthenticationError("Invalid browser session token signature")
    try:
        payload_bytes = _b64decode(p_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        raise AuthenticationError("Corrupt browser session token payload")
    exp = payload.get("exp")
    if exp is not None and time.time() > exp:
        raise AuthenticationError("Browser session token has expired")
    return {
        "session_id": uuid.UUID(payload["session_id"]),
        "organization_id": uuid.UUID(payload["org_id"]),
        "user_id": uuid.UUID(payload["user_id"]) if payload.get("user_id") else None,
        "browser_id": payload.get("browser_id", ""),
        "client_version": payload.get("client_version", "2.0.0"),
        "expires_at": exp,
    }


def verify_and_authorize_browser_session_token(
    token: str,
    expected_org_id: Optional[uuid.UUID] = None,
) -> AuthenticatedActor:
    """Verify signed browser session token and construct AuthenticatedActor with BROWSER_SESSION identity."""
    session_data = verify_browser_session_token(token)
    session_id = session_data["session_id"]
    org_id = session_data["organization_id"]

    if expected_org_id and org_id != expected_org_id:
        raise AuthorizationError(
            f"Cross-tenant access rejected: browser session belongs to org {org_id}, requested {expected_org_id}"
        )

    # Check revoked sessions in gateway registry
    try:
        from services.api.app.agents.browser.gateway import browser_gateway
        if session_id in browser_gateway._revoked_sessions:
            raise AuthenticationError("Browser session has been revoked")
    except ImportError:
        pass

    return AuthenticatedActor(
        actor_id=f"browser_session_{session_id.hex[:8]}",
        organization_id=org_id,
        actor_type="BROWSER_SESSION",
        session_id=session_id,
        is_authenticated=True,
    )

