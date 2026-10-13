import asyncio
import logging
import secrets
import string
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set
from fastapi import WebSocket

from packages.agent_core.tools import BrowserToolRegistry
from packages.shared_types.agent import AgentState, SessionStatus
from packages.shared_types.browser_protocol import (
    BrowserCommand,
    BrowserCommandResult,
    BrowserCommandType,
    CommandExecutionStatus,
    ExtensionSessionState,
    PageState,
)
from services.api.app.agents.research.validators import (
    SSRFValidationError,
    validate_and_sanitize_target_url,
)
from services.api.app.services.event_dispatcher import EventDispatcher

logger = logging.getLogger("techverse.agent.browser.gateway")


class BrowserGatewayException(Exception):
    """Base exception for browser gateway errors."""
    pass


class SessionNotConnectedException(BrowserGatewayException):
    """Raised when attempting to command a disconnected browser session."""
    pass


class CommandValidationException(BrowserGatewayException):
    """Raised when command parameters fail security or schema verification."""
    pass


class BrowserGatewayManager:
    """
    Central WebSocket gateway and session manager between FastAPI backend and Chrome extension.
    Enforces authentication, pairing challenges, command timeouts, SSRF protections, and event dispatching.
    """

    def __init__(self):
        # session_id -> WebSocket
        self._active_connections: Dict[uuid.UUID, WebSocket] = {}
        # session_id -> org_id
        self._session_orgs: Dict[uuid.UUID, uuid.UUID] = {}
        # session_id -> user_id
        self._session_users: Dict[uuid.UUID, Optional[uuid.UUID]] = {}
        # command_id -> {"future": asyncio.Future, "session_id": uuid.UUID, "org_id": uuid.UUID, "issued_at": float}
        self._pending_commands: Dict[uuid.UUID, Dict[str, Any]] = {}
        # session_id -> latest PageState
        self._page_states: Dict[uuid.UUID, PageState] = {}
        # session_id -> ExtensionSessionState
        self._session_states: Dict[uuid.UUID, ExtensionSessionState] = {}

        # Pairing store: challenge_code -> {challenge_code, token, org_id, user_id, expires_at}
        self._pairing_challenges: Dict[str, Dict[str, Any]] = {}
        # Active session tokens: token -> {session_id, org_id, user_id, expires_at}
        self._session_tokens: Dict[str, Dict[str, Any]] = {}
        # Revoked session set
        self._revoked_sessions: Set[uuid.UUID] = set()

    # --- Pairing & Token Authentication ---

    def create_pairing_challenge(
        self,
        org_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        ttl_seconds: int = 300,
    ) -> Dict[str, Any]:
        """Generate a short-lived, single-use pairing challenge code for extension pairing."""
        chars = string.ascii_uppercase + string.digits
        # Format: TV-XXXX-XXXX
        code_part1 = "".join(secrets.choice(chars) for _ in range(4))
        code_part2 = "".join(secrets.choice(chars) for _ in range(4))
        challenge_code = f"TV-{code_part1}-{code_part2}"

        challenge_token = secrets.token_urlsafe(32)
        expires_at = time.time() + ttl_seconds

        record = {
            "challenge_code": challenge_code,
            "challenge_token": challenge_token,
            "organization_id": org_id,
            "user_id": user_id,
            "expires_at": expires_at,
        }
        self._pairing_challenges[challenge_code] = record

        # Cleanup expired challenges
        self._cleanup_expired_challenges()

        return {
            "pairing_code": challenge_code,
            "expires_in_seconds": ttl_seconds,
            "expires_at": datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat(),
        }

    def verify_and_pair(
        self,
        pairing_code: str,
        session_id: uuid.UUID,
        browser_id: str,
        client_version: str = "2.0.0",
        token_ttl_seconds: int = 86400 * 7,
    ) -> Dict[str, Any]:
        """Verify single-use pairing code and issue a persistent cryptographically signed extension session token."""
        code = pairing_code.strip().upper()
        record = self._pairing_challenges.get(code)
        if not record:
            raise BrowserGatewayException("Invalid or non-existent pairing code")

        if time.time() > record["expires_at"]:
            self._pairing_challenges.pop(code, None)
            raise BrowserGatewayException("Pairing code has expired")

        # Invalidate pairing challenge immediately (single use)
        self._pairing_challenges.pop(code, None)

        from services.api.app.core.auth import create_browser_session_token
        session_token = create_browser_session_token(
            session_id=session_id,
            org_id=record["organization_id"],
            user_id=record["user_id"],
            browser_id=browser_id,
            client_version=client_version,
            expires_in_seconds=token_ttl_seconds,
        )
        expires_at = time.time() + token_ttl_seconds

        token_record = {
            "session_id": session_id,
            "organization_id": record["organization_id"],
            "user_id": record["user_id"],
            "browser_id": browser_id,
            "client_version": client_version,
            "expires_at": expires_at,
        }
        self._session_tokens[session_token] = token_record
        self._session_orgs[session_id] = record["organization_id"]
        self._session_users[session_id] = record["user_id"]
        self._session_states[session_id] = ExtensionSessionState.AUTHORIZED

        logger.info(f"Extension paired successfully: session_id={session_id}, org_id={record['organization_id']}")

        return {
            "session_id": session_id,
            "token": session_token,
            "organization_id": record["organization_id"],
            "expires_at": datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat(),
        }

    def validate_session_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate token passed to WebSocket or gateway."""
        if not token:
            return None
        record = self._session_tokens.get(token)
        if record:
            if time.time() > record["expires_at"]:
                self._session_tokens.pop(token, None)
                return None
            if record.get("session_id") in self._revoked_sessions:
                return None
            return record

        # Fallback to cryptographic signature verification
        try:
            from services.api.app.core.auth import verify_browser_session_token
            decoded = verify_browser_session_token(token)
            sess_id = decoded["session_id"]
            if sess_id in self._revoked_sessions:
                return None
            self._session_tokens[token] = decoded
            self._session_orgs[sess_id] = decoded["organization_id"]
            self._session_users[sess_id] = decoded.get("user_id")
            self._session_states[sess_id] = ExtensionSessionState.AUTHORIZED
            return decoded
        except Exception as e:
            logger.debug(f"Session token verification error: {e}")
            return None

    def revoke_session(self, session_id: uuid.UUID) -> bool:
        """Revoke all tokens and disconnect session."""
        self._revoked_sessions.add(session_id)
        tokens_to_remove = [
            t for t, r in self._session_tokens.items() if r.get("session_id") == session_id
        ]
        for t in tokens_to_remove:
            self._session_tokens.pop(t, None)

        self._session_states[session_id] = ExtensionSessionState.STOPPED
        if session_id in self._active_connections:
            # Cancel pending commands
            self._cancel_session_commands(session_id, "Session revoked by user")
        return True

    def _cleanup_expired_challenges(self) -> None:
        now = time.time()
        expired = [c for c, r in self._pairing_challenges.items() if r["expires_at"] < now]
        for c in expired:
            self._pairing_challenges.pop(c, None)

    # --- Connection Management ---

    async def register_connection(
        self,
        session_id: uuid.UUID,
        websocket: WebSocket,
        org_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Register active WebSocket connection from Chrome extension."""
        self._active_connections[session_id] = websocket
        self._session_orgs[session_id] = org_id
        self._session_users[session_id] = user_id
        self._session_states[session_id] = ExtensionSessionState.CONNECTED

        await EventDispatcher.dispatch(
            event_type="browser.connected",
            data={
                "session_id": str(session_id),
                "organization_id": str(org_id),
                "user_id": str(user_id) if user_id else None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            organization_id=org_id,
        )
        logger.info(f"Browser extension WebSocket connected: session_id={session_id}")

    async def unregister_connection(self, session_id: uuid.UUID) -> None:
        """Handle extension disconnection safely."""
        self._active_connections.pop(session_id, None)
        self._session_states[session_id] = ExtensionSessionState.DISCONNECTED

        # Fail-safe: cancel all pending commands for this session
        self._cancel_session_commands(session_id, "Browser extension disconnected")

        org_id = self._session_orgs.get(session_id)
        if org_id:
            await EventDispatcher.dispatch(
                event_type="browser.disconnected",
                data={
                    "session_id": str(session_id),
                    "organization_id": str(org_id),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                organization_id=org_id,
            )
        logger.info(f"Browser extension WebSocket disconnected: session_id={session_id}")

    def is_connected(self, session_id: uuid.UUID) -> bool:
        return session_id in self._active_connections

    def get_session_state(self, session_id: uuid.UUID) -> ExtensionSessionState:
        return self._session_states.get(session_id, ExtensionSessionState.DISCONNECTED)

    def get_page_state(self, session_id: uuid.UUID) -> Optional[PageState]:
        return self._page_states.get(session_id)

    # --- Command Dispatch & Validation ---

    async def send_command(
        self,
        command: BrowserCommand,
        timeout_seconds: float = 15.0,
        expected_org_id: Optional[uuid.UUID] = None,
    ) -> BrowserCommandResult:
        """
        Send a validated structured command to the Chrome extension and await result.
        Enforces organization isolation, SSRF prevention, tool registry schema validation, and timeouts.
        """
        session_id = command.session_id
        ws = self._active_connections.get(session_id)
        if not ws:
            raise SessionNotConnectedException(f"Browser session {session_id} is not connected")

        org_id = self._session_orgs.get(session_id)
        if expected_org_id and org_id and org_id != expected_org_id:
            raise CommandValidationException(
                f"Cross-organization session command rejected: session belongs to org {org_id}, not {expected_org_id}"
            )

        # 1. Tool registry check
        tool_name = command.type.value.lower()
        if not BrowserToolRegistry.is_valid_tool(tool_name):
            # Check uppercase alias or outreach tool
            if command.type != BrowserCommandType.EXECUTE_APPROVED_OUTREACH:
                raise CommandValidationException(f"Unregistered browser tool: {command.type.value}")

        # 2. SSRF check for navigation commands
        if command.type in (BrowserCommandType.OPEN_PAGE, BrowserCommandType.NAVIGATE):
            target_url = command.payload.get("url") or command.payload.get("target_url")
            if target_url:
                try:
                    safe_url = validate_and_sanitize_target_url(target_url)
                    command.payload["url"] = safe_url
                    command.payload["target_url"] = safe_url
                except SSRFValidationError as e:
                    if org_id:
                        await EventDispatcher.dispatch(
                            event_type="browser.action.blocked",
                            data={
                                "session_id": str(session_id),
                                "command_id": str(command.command_id),
                                "reason": f"SSRF blocked: {str(e)}",
                                "target_url": target_url,
                            },
                            organization_id=org_id,
                        )
                    return BrowserCommandResult(
                        command_id=command.command_id,
                        session_id=session_id,
                        success=False,
                        status=CommandExecutionStatus.BLOCKED,
                        error=f"Navigation blocked by SSRF policy: {str(e)}",
                        correlation_id=command.correlation_id,
                    )

        # 3. Create tracking future bound to session and organization
        loop = asyncio.get_running_loop()
        future: asyncio.Future[BrowserCommandResult] = loop.create_future()
        self._pending_commands[command.command_id] = {
            "future": future,
            "session_id": session_id,
            "org_id": org_id,
            "issued_at": time.time(),
        }

        org_id = self._session_orgs.get(session_id)
        if org_id:
            await EventDispatcher.dispatch(
                event_type="browser.command.issued",
                data={
                    "session_id": str(session_id),
                    "command_id": str(command.command_id),
                    "type": command.type.value,
                    "correlation_id": command.correlation_id,
                },
                organization_id=org_id,
            )

        start_time = time.time()
        try:
            # Send message frame to extension
            message_frame = {
                "frame_type": "COMMAND",
                "command": command.model_dump(mode="json"),
            }
            await ws.send_json(message_frame)

            # Wait for result with timeout
            result = await asyncio.wait_for(future, timeout=timeout_seconds)
            duration_ms = (time.time() - start_time) * 1000.0
            result.duration_ms = duration_ms

            if org_id:
                event_name = "browser.command.completed" if result.success else "browser.command.failed"
                await EventDispatcher.dispatch(
                    event_type=event_name,
                    data={
                        "session_id": str(session_id),
                        "command_id": str(command.command_id),
                        "status": result.status.value,
                        "duration_ms": duration_ms,
                        "correlation_id": command.correlation_id,
                    },
                    organization_id=org_id,
                )
            return result

        except asyncio.TimeoutError:
            self._pending_commands.pop(command.command_id, None)
            duration_ms = (time.time() - start_time) * 1000.0
            logger.warning(f"Command {command.command_id} timed out after {timeout_seconds}s")
            return BrowserCommandResult(
                command_id=command.command_id,
                session_id=session_id,
                success=False,
                status=CommandExecutionStatus.EXPIRED,
                error=f"Command timed out after {timeout_seconds} seconds",
                duration_ms=duration_ms,
                correlation_id=command.correlation_id,
            )
        except Exception as e:
            self._pending_commands.pop(command.command_id, None)
            duration_ms = (time.time() - start_time) * 1000.0
            logger.error(f"Error sending command {command.command_id}: {e}")
            return BrowserCommandResult(
                command_id=command.command_id,
                session_id=session_id,
                success=False,
                status=CommandExecutionStatus.FAILED,
                error=str(e),
                duration_ms=duration_ms,
                correlation_id=command.correlation_id,
            )

    # --- Incoming Frame Handling ---

    async def handle_incoming_frame(
        self,
        session_id: uuid.UUID,
        frame: Dict[str, Any],
    ) -> None:
        """Handle incoming frame received from extension over WebSocket."""
        frame_type = frame.get("frame_type")
        payload = frame.get("payload", {})
        org_id = self._session_orgs.get(session_id)

        if frame_type == "RESULT":
            command_id_raw = payload.get("command_id")
            if command_id_raw:
                try:
                    cmd_id = uuid.UUID(str(command_id_raw))
                    cmd_record = self._pending_commands.get(cmd_id)
                    if cmd_record:
                        # Verify session ownership: only the targeted session may resolve the command
                        if cmd_record.get("session_id") != session_id:
                            logger.warning(
                                f"Cross-session result injection attempt blocked: cmd_id={cmd_id}, "
                                f"target_session={cmd_record.get('session_id')}, reporting_session={session_id}"
                            )
                            return
                        self._pending_commands.pop(cmd_id, None)
                        future = cmd_record.get("future")
                        if future and not future.done():
                            status_str = payload.get("status", "SUCCESS")
                            status_enum = (
                                CommandExecutionStatus(status_str)
                                if status_str in CommandExecutionStatus.__members__
                                else CommandExecutionStatus.SUCCESS
                            )
                            result = BrowserCommandResult(
                                command_id=cmd_id,
                                session_id=session_id,
                                success=payload.get("success", True),
                                status=status_enum,
                                result=payload.get("result", {}),
                                error=payload.get("error"),
                                duration_ms=payload.get("duration_ms", 0.0),
                                correlation_id=payload.get("correlation_id", ""),
                            )
                            future.set_result(result)
                except Exception as e:
                    logger.error(f"Error resolving command result: {e}")

        elif frame_type == "PAGE_STATE":
            try:
                page_state = PageState.model_validate(payload)
                self._page_states[session_id] = page_state
                if org_id:
                    await EventDispatcher.dispatch(
                        event_type="browser.page.changed",
                        data={
                            "session_id": str(session_id),
                            "url": page_state.url,
                            "title": page_state.title,
                            "page_type": page_state.page_type.value,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                        organization_id=org_id,
                    )
            except Exception as e:
                logger.error(f"Invalid page_state frame: {e}")

        elif frame_type == "OBSERVATION":
            if org_id:
                await EventDispatcher.dispatch(
                    event_type="browser.observation.created",
                    data={
                        "session_id": str(session_id),
                        "url": payload.get("url"),
                        "title": payload.get("title"),
                        "page_type": payload.get("page_type"),
                        "visible_text_snippet": (payload.get("visible_text") or "")[:200],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                    organization_id=org_id,
                )

                # Persist observation and invoke downstream processing pipeline
                url = payload.get("url") or ""
                visible_text = payload.get("visible_text") or ""
                if url and visible_text:
                    try:
                        from services.api.app.core.database import async_session_factory
                        from services.api.app.services.agent_service import AgentService

                        async with async_session_factory() as db_session:
                            agent_svc = AgentService(db_session)
                            await agent_svc.observe_and_process_page(
                                org_id=org_id,
                                session_id=session_id,
                                url=url,
                                visible_text=visible_text,
                                recipient_handle=payload.get("recipient_handle"),
                                profile_url=payload.get("profile_url"),
                            )
                    except Exception as e:
                        logger.warning(f"Error processing browser observation pipeline: {e}")

        elif frame_type == "STATUS_UPDATE":
            status_str = payload.get("status")
            if status_str and status_str in ExtensionSessionState.__members__:
                self._session_states[session_id] = ExtensionSessionState(status_str)

        elif frame_type == "SECURITY_ALERT":
            reason = payload.get("reason", "Challenge or security check detected")
            challenge_type = payload.get("challenge_type", "CAPTCHA")
            self._session_states[session_id] = ExtensionSessionState.BLOCKED
            if org_id:
                await EventDispatcher.dispatch(
                    event_type="browser.action.blocked",
                    data={
                        "session_id": str(session_id),
                        "reason": reason,
                        "challenge_type": challenge_type,
                        "url": payload.get("url"),
                    },
                    organization_id=org_id,
                )

        elif frame_type == "DELIVERY_UNKNOWN":
            draft_id = payload.get("draft_id")
            reason = payload.get("reason", "Action executed but send confirmation could not be verified")
            if org_id:
                await EventDispatcher.dispatch(
                    event_type="outreach.delivery.unknown",
                    data={
                        "session_id": str(session_id),
                        "draft_id": str(draft_id) if draft_id else None,
                        "reason": reason,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                    organization_id=org_id,
                )

    def _cancel_session_commands(self, session_id: uuid.UUID, reason: str) -> None:
        """Cancel only pending command futures belonging to this specific session."""
        cancelled_ids = []
        for cmd_id, cmd_record in list(self._pending_commands.items()):
            if cmd_record.get("session_id") == session_id:
                future = cmd_record.get("future")
                if future and not future.done():
                    result = BrowserCommandResult(
                        command_id=cmd_id,
                        session_id=session_id,
                        success=False,
                        status=CommandExecutionStatus.CANCELLED,
                        error=reason,
                        correlation_id=str(uuid.uuid4()),
                    )
                    future.set_result(result)
                cancelled_ids.append(cmd_id)
        for cid in cancelled_ids:
            self._pending_commands.pop(cid, None)


# Singleton instance
browser_gateway = BrowserGatewayManager()
