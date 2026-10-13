import uuid
from typing import Optional
from fastapi import Depends, Header, HTTPException, Query, WebSocket, status
from sqlalchemy.ext.asyncio import AsyncSession

from packages.config.settings import settings
from services.api.app.core.auth import (
    AuthenticationError,
    AuthorizationError,
    AuthenticatedActor,
    DEFAULT_DEV_ORG_ID,
    create_access_token,
    create_api_key,
    verify_access_token,
    verify_api_key,
    verify_and_authorize_browser_session_token,
)
from services.api.app.core.database import async_session_factory, get_db
from services.api.app.repositories.crm import OrganizationRepository


async def get_authenticated_actor(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_organization_id: Optional[str] = Header(None, alias="X-Organization-ID"),
    db: AsyncSession = Depends(get_db),
) -> AuthenticatedActor:
    """
    Authenticates caller identity and authorizes tenant context.
    - Production Mode:
        1. Requires valid signed Bearer token or valid signed API Key. Arbitrary non-empty tokens are strictly rejected.
        2. Organization identity is bound directly to the authenticated credential.
        3. If client passes X-Organization-ID that does not match credential's org_id, access is rejected (403).
        4. Development fallbacks are strictly disabled.
    - Development/Test Mode:
        1. If credentials provided, verifies them and binds to authenticated org.
        2. If no credentials provided, preserves isolated local development mode with DEFAULT_DEV_ORG_ID.
    """
    org_repo = OrganizationRepository(db)

    # Extract raw token if present
    token: Optional[str] = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    elif x_api_key:
        token = x_api_key.strip()

    # 1. Production Mode: Strict Cryptographic Verification
    if settings.ENVIRONMENT == "production":
        if not x_organization_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required X-Organization-ID header in production",
            )
        if not token:
            raise AuthenticationError(
                "Authentication credentials (Bearer token or X-API-Key) required in production"
            )

        try:
            req_org_id = uuid.UUID(x_organization_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid X-Organization-ID UUID header",
            )

        authenticated_org_id: Optional[uuid.UUID] = None
        actor_id: str = "authenticated_user"
        actor_type: str = "USER"
        session_id: Optional[uuid.UUID] = None

        # Verify structured API key, browser session token, or JWT access token
        if token.startswith("tv_key_"):
            authenticated_org_id = verify_api_key(token)
            actor_id = f"api_client_{authenticated_org_id.hex[:8]}"
            actor_type = "API_KEY"
            if req_org_id != authenticated_org_id:
                raise AuthorizationError(
                    f"Forged organization identity: token bound to {authenticated_org_id}, header specified {req_org_id}"
                )
        elif token.startswith("tv_sess_"):
            sess_actor = verify_and_authorize_browser_session_token(token, req_org_id)
            authenticated_org_id = sess_actor.organization_id
            actor_id = sess_actor.actor_id
            actor_type = sess_actor.actor_type
            session_id = sess_actor.session_id
        else:
            payload = verify_access_token(token)
            authenticated_org_id = uuid.UUID(payload["org_id"])
            actor_id = payload.get("sub", "authenticated_user")
            actor_type = payload.get("role", "USER")
            if req_org_id != authenticated_org_id:
                raise AuthorizationError(
                    f"Forged organization identity: token bound to {authenticated_org_id}, header specified {req_org_id}"
                )

        # Verify organization exists in database
        org = await org_repo.get_by_id(authenticated_org_id)
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Organization {authenticated_org_id} bound to credentials not found",
            )

        return AuthenticatedActor(
            actor_id=actor_id,
            organization_id=authenticated_org_id,
            actor_type=actor_type,
            session_id=session_id,
            is_authenticated=True,
        )

    # 2. Development / Test Mode
    if token:
        try:
            req_org_dev = None
            if x_organization_id:
                try:
                    req_org_dev = uuid.UUID(x_organization_id)
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid X-Organization-ID UUID header",
                    )

            if token.startswith("tv_key_"):
                bound_org = verify_api_key(token)
                actor_id = f"api_client_{bound_org.hex[:8]}"
                actor_type = "API_KEY"
                session_id = None
                if req_org_dev and req_org_dev != bound_org:
                    raise AuthorizationError(
                        f"Cross-tenant access rejected: credentials belong to {bound_org}"
                    )
            elif token.startswith("tv_sess_"):
                return verify_and_authorize_browser_session_token(token, req_org_dev)
            elif token in ("dev-token", "dev-test-token") or token.startswith("tv_dev_"):
                bound_org = req_org_dev or DEFAULT_DEV_ORG_ID
                actor_id = "dev_user"
                actor_type = "USER"
                session_id = None
            else:
                payload = verify_access_token(token)
                bound_org = uuid.UUID(payload["org_id"])
                actor_id = payload.get("sub", "authenticated_user")
                actor_type = payload.get("role", "USER")
                session_id = None
                if req_org_dev and req_org_dev != bound_org:
                    raise AuthorizationError(
                        f"Cross-tenant access rejected: credentials belong to {bound_org}"
                    )

            return AuthenticatedActor(
                actor_id=actor_id,
                organization_id=bound_org,
                actor_type=actor_type,
                session_id=session_id,
                is_authenticated=True,
            )
        except (AuthenticationError, AuthorizationError):
            raise
        except Exception:
            raise AuthenticationError("Invalid development credentials")

    # If no token in development mode: Check explicit X-Organization-ID or fallback
    if x_organization_id:
        try:
            target_org_id = uuid.UUID(x_organization_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid X-Organization-ID UUID header",
            )
        org = await org_repo.get_by_id(target_org_id)
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Organization {target_org_id} not found",
            )
        return AuthenticatedActor(
            actor_id="dev_user",
            organization_id=target_org_id,
            actor_type="USER",
            is_authenticated=True,
        )

    # Default dev org fallback for local tooling
    dev_org = await org_repo.get_by_id(DEFAULT_DEV_ORG_ID)
    if not dev_org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Development organization {DEFAULT_DEV_ORG_ID} not found or uninitialized",
        )
    return AuthenticatedActor(
        actor_id="dev_user",
        organization_id=DEFAULT_DEV_ORG_ID,
        actor_type="USER",
        is_authenticated=True,
    )


async def get_current_org_id(
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
) -> uuid.UUID:
    """Extract authorized organization ID from authenticated context."""
    return actor.organization_id


async def authenticate_ws_actor(
    websocket: WebSocket,
    token: Optional[str] = None,
    x_organization_id: Optional[str] = None,
    db: Optional[AsyncSession] = None,
) -> AuthenticatedActor:
    """
    Authenticate WebSocket handshake before establishing subscription.
    Extracts token from query param, headers, or first protocol message.
    Strictly prevents cross-tenant subscription in production and dev.
    """
    # Try token from query param or headers
    auth_token = token
    if not auth_token:
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            auth_token = auth_header[7:].strip()
        elif websocket.headers.get("x-api-key"):
            auth_token = websocket.headers.get("x-api-key")

    if not x_organization_id:
        x_organization_id = websocket.headers.get("x-organization-id") or websocket.query_params.get("org_id")

    if db:
        return await get_authenticated_actor(
            authorization=f"Bearer {auth_token}" if auth_token else None,
            x_api_key=None,
            x_organization_id=x_organization_id,
            db=db,
        )

    try:
        async with async_session_factory() as session:
            return await get_authenticated_actor(
                authorization=f"Bearer {auth_token}" if auth_token else None,
                x_api_key=None,
                x_organization_id=x_organization_id,
                db=session,
            )
    except Exception as exc:
        if isinstance(exc, (HTTPException, AuthenticationError, AuthorizationError)):
            raise
        # When DB connection fails (e.g. isolated test environments), still strictly verify token and anti-forgery
        if auth_token:
            req_ws_org = uuid.UUID(x_organization_id) if x_organization_id else None
            if auth_token.startswith("tv_key_"):
                bound_org = verify_api_key(auth_token)
                if req_ws_org and req_ws_org != bound_org:
                    raise AuthorizationError(f"Forged organization identity: token bound to {bound_org}, header specified {req_ws_org}")
                return AuthenticatedActor(actor_id=f"api_client_{bound_org.hex[:8]}", organization_id=bound_org, actor_type="API_KEY", is_authenticated=True)
            elif auth_token.startswith("tv_sess_"):
                return verify_and_authorize_browser_session_token(auth_token, req_ws_org)
            else:
                payload = verify_access_token(auth_token)
                bound_org = uuid.UUID(payload["org_id"])
                if req_ws_org and req_ws_org != bound_org:
                    raise AuthorizationError(
                        f"Forged organization identity: token bound to {bound_org}, header specified {x_organization_id}"
                    )
                return AuthenticatedActor(
                    actor_id=payload.get("sub", "authenticated_user"),
                    organization_id=bound_org,
                    actor_type=payload.get("role", "USER"),
                    is_authenticated=True,
                )
        raise
