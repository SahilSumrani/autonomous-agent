import asyncio
import hashlib
import logging
import uuid
from typing import Any, Callable, Dict, List, Optional

from packages.shared_types.browser_protocol import (
    BrowserCommand,
    BrowserCommandResult,
    BrowserCommandType,
    CommandExecutionStatus,
)
from services.api.app.agents.browser.gateway import (
    BrowserGatewayManager,
    browser_gateway,
)

from urllib.parse import urlparse
from services.api.app.agents.research.validators import (
    validate_and_sanitize_target_url,
    SSRFValidationError,
)

logger = logging.getLogger("techverse.agent.prospecting.driver")


class BrowserCommandDriver:
    """
    Autonomous browser driver executing bounded navigation, reading, and scrolling
    through the authorized Chrome extension WebSocket gateway.
    Enforces tenant and session isolation, bounded loops, and duplicate-content detection.
    """

    def __init__(
        self,
        session_id: uuid.UUID,
        org_id: uuid.UUID,
        job_id: uuid.UUID,
        gateway: Optional[BrowserGatewayManager] = None,
    ):
        self.session_id = session_id
        self.org_id = org_id
        self.job_id = job_id
        self.gateway = gateway or browser_gateway

    def is_connected(self) -> bool:
        return self.gateway.is_connected(self.session_id)

    async def navigate(
        self,
        target_url: str,
        tab_id: Optional[int] = None,
        timeout_seconds: float = 25.0,
    ) -> BrowserCommandResult:
        """
        Instruct the connected extension to navigate the target tab to a validated URL.
        Validates target URL against SSRF and security policies prior to dispatch.
        """
        correlation_id = str(uuid.uuid4())

        # 1. SSRF & Scheme Validation
        lower_raw = (target_url or "").strip().lower()
        if lower_raw.startswith(("javascript:", "data:", "about:", "file:", "chrome:", "edge:", "blob:")):
            return BrowserCommandResult(
                command_id=uuid.uuid4(),
                session_id=self.session_id,
                success=False,
                status=CommandExecutionStatus.BLOCKED,
                error=f"Blocked unsafe URL scheme: {lower_raw.split(':', 1)[0]}",
                duration_ms=0.0,
                correlation_id=correlation_id,
            )

        try:
            clean_url = validate_and_sanitize_target_url(target_url)
            parsed = urlparse(clean_url)
            if parsed.username or parsed.password:
                raise SSRFValidationError("Credentials in URL are prohibited")
        except Exception as e:
            logger.warning(f"Job {self.job_id}: Navigation blocked by security check: {e}")
            return BrowserCommandResult(
                command_id=uuid.uuid4(),
                session_id=self.session_id,
                success=False,
                status=CommandExecutionStatus.BLOCKED,
                error=f"Blocked by URL security policy: {e}",
                duration_ms=0.0,
                correlation_id=correlation_id,
            )

        # 2. Authorization / Connection Check
        if not self.is_connected():
            return BrowserCommandResult(
                command_id=uuid.uuid4(),
                session_id=self.session_id,
                success=False,
                status=CommandExecutionStatus.FAILED,
                error="Browser extension session is not connected",
                duration_ms=0.0,
                correlation_id=correlation_id,
            )

        # 3. Dispatch NAVIGATE command
        payload: Dict[str, Any] = {
            "session_id": str(self.session_id),
            "target_url": clean_url,
            "url": clean_url,
            "correlation_id": correlation_id,
        }
        if tab_id is not None:
            payload["tab_id"] = tab_id

        command = BrowserCommand(
            session_id=self.session_id,
            type=BrowserCommandType.NAVIGATE,
            payload=payload,
            correlation_id=correlation_id,
        )
        logger.info(f"Job {self.job_id}: Navigating Chrome tab to {clean_url}")
        return await self.gateway.send_command(
            command,
            timeout_seconds=timeout_seconds,
            expected_org_id=self.org_id,
        )

    async def open_page(self, url: str, timeout_seconds: float = 25.0) -> BrowserCommandResult:
        """Instruct the connected extension to navigate to a sanitized URL."""
        return await self.navigate(target_url=url, timeout_seconds=timeout_seconds)

    async def stop(self, timeout_seconds: float = 5.0) -> BrowserCommandResult:
        """Notify connected extension that autonomous browser control has ended."""
        command = BrowserCommand(
            session_id=self.session_id,
            type=BrowserCommandType.STOP,
            payload={"session_id": str(self.session_id)},
            correlation_id=str(uuid.uuid4()),
        )
        return await self.gateway.send_command(
            command,
            timeout_seconds=timeout_seconds,
            expected_org_id=self.org_id,
        )

    async def read_page(self, timeout_seconds: float = 15.0) -> Dict[str, Any]:
        """Request visible text and metadata extraction from current page."""
        command = BrowserCommand(
            session_id=self.session_id,
            type=BrowserCommandType.READ_PAGE,
            payload={},
            correlation_id=str(uuid.uuid4()),
        )
        res = await self.gateway.send_command(
            command,
            timeout_seconds=timeout_seconds,
            expected_org_id=self.org_id,
        )
        if not res.success:
            logger.warning(f"Job {self.job_id}: read_page failed: {res.error}")
            return {}

        return res.result or {}

    async def scroll(
        self,
        direction: str = "down",
        distance: int = 600,
        timeout_seconds: float = 10.0,
    ) -> BrowserCommandResult:
        """Scroll page viewport incrementally."""
        command = BrowserCommand(
            session_id=self.session_id,
            type=BrowserCommandType.SCROLL,
            payload={"direction": direction, "distance": distance},
            correlation_id=str(uuid.uuid4()),
        )
        return await self.gateway.send_command(
            command,
            timeout_seconds=timeout_seconds,
            expected_org_id=self.org_id,
        )

    async def click(
        self,
        selector: Optional[str] = None,
        text: Optional[str] = None,
        selector_type: str = "selector",
        timeout_seconds: float = 10.0,
    ) -> BrowserCommandResult:
        """Click a safe navigational or interactive element."""
        payload: Dict[str, Any] = {}
        if selector:
            payload["selector"] = selector
        if text:
            payload["text"] = text
        if selector and not text:
            payload["target"] = {"selector_type": selector_type, "value": selector}

        command = BrowserCommand(
            session_id=self.session_id,
            type=BrowserCommandType.CLICK,
            payload=payload,
            correlation_id=str(uuid.uuid4()),
        )
        return await self.gateway.send_command(
            command,
            timeout_seconds=timeout_seconds,
            expected_org_id=self.org_id,
        )

    async def type_text(
        self,
        text: str,
        selector: Optional[str] = None,
        clear_first: bool = True,
        timeout_seconds: float = 12.0,
    ) -> BrowserCommandResult:
        """Type text into a target or auto-discovered search/form field."""
        command = BrowserCommand(
            session_id=self.session_id,
            type=BrowserCommandType.TYPE_TEXT,
            payload={
                "text": text,
                "selector": selector or "auto",
                "clear_first": clear_first,
            },
            correlation_id=str(uuid.uuid4()),
        )
        return await self.gateway.send_command(
            command,
            timeout_seconds=timeout_seconds,
            expected_org_id=self.org_id,
        )

    async def press_key(
        self,
        key: str = "Enter",
        selector: Optional[str] = None,
        timeout_seconds: float = 10.0,
    ) -> BrowserCommandResult:
        """Dispatch key press event (e.g. Enter to submit search)."""
        command = BrowserCommand(
            session_id=self.session_id,
            type=BrowserCommandType.PRESS_KEY,
            payload={"key": key, "selector": selector},
            correlation_id=str(uuid.uuid4()),
        )
        return await self.gateway.send_command(
            command,
            timeout_seconds=timeout_seconds,
            expected_org_id=self.org_id,
        )

    async def find_search_input(self, timeout_seconds: float = 8.0) -> Dict[str, Any]:
        """Detect visible search input on current page."""
        command = BrowserCommand(
            session_id=self.session_id,
            type=BrowserCommandType.FIND_SEARCH_INPUT,
            payload={},
            correlation_id=str(uuid.uuid4()),
        )
        res = await self.gateway.send_command(
            command,
            timeout_seconds=timeout_seconds,
            expected_org_id=self.org_id,
        )
        if res.success and res.result:
            return res.result
        return {"found": False}

    async def interactive_search(
        self,
        query: str,
        search_input_selector: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute full adaptive search interaction:
        Find search input -> Type query -> Submit search (Enter) -> Wait for results.
        """
        logger.info(f"Job {self.job_id}: Initiating interactive search for '{query}'")

        # 1. Discover search input if selector not specified
        target_selector = search_input_selector
        if not target_selector:
            discovery = await self.find_search_input()
            if discovery.get("found") and discovery.get("selector"):
                target_selector = discovery.get("selector")
                logger.info(f"Job {self.job_id}: Discovered search input with selector '{target_selector}'")

        # 2. Type query
        type_res = await self.type_text(text=query, selector=target_selector)
        if not type_res.success:
            err = type_res.error or "TYPE_FAILED"
            logger.warning(f"Job {self.job_id}: Failed to type search query: {err}")
            return {"success": False, "error": err}

        # 3. Submit search via Enter
        await asyncio.sleep(0.3)
        press_res = await self.press_key(key="Enter", selector=target_selector)
        if not press_res.success:
            logger.warning(f"Job {self.job_id}: Key press submit failed: {press_res.error}")

        # 4. Wait for dynamic content to load
        await asyncio.sleep(2.0)
        await self.wait_for_ready()

        return {"success": True, "query": query, "selector": target_selector}

    async def wait_for_ready(self, max_wait_seconds: float = 8.0, poll_interval: float = 0.5) -> bool:
        """Wait for page load completion state."""
        start = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start < max_wait_seconds:
            page_state = self.gateway.get_page_state(self.session_id)
            if page_state and not page_state.is_loading:
                return True
            await asyncio.sleep(poll_interval)
        return True

    @staticmethod
    def compute_content_hash(text: str) -> str:
        """Calculate content hash for duplicate or no-new-content detection."""
        clean = " ".join(text.split()).strip()
        return hashlib.sha256(clean.encode("utf-8")).hexdigest()

    async def controlled_scroll_and_read(
        self,
        max_scrolls: int = 5,
        scroll_distance: int = 600,
        settle_delay: float = 1.0,
        initial_observation: Optional[Dict[str, Any]] = None,
        on_observation_callback: Optional[Callable[[Dict[str, Any]], Any]] = None,
        consecutive_unchanged_threshold: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Controlled scrolling loop:
        1. Reads initial page content (or uses provided initial_observation)
        2. Loops up to max_scrolls:
           - scrolls down
           - waits for content stabilization
           - reads newly revealed content
           - detects duplicate/stagnant content; stops if no new content
        """
        observations: List[Dict[str, Any]] = []
        seen_hashes = set()

        # Initial read or reuse provided observation
        initial_obs = initial_observation if initial_observation is not None else await self.read_page()
        if initial_obs:
            text = initial_obs.get("visible_text") or ""
            c_hash = self.compute_content_hash(text)
            seen_hashes.add(c_hash)
            initial_obs["content_hash"] = c_hash
            observations.append(initial_obs)
            if on_observation_callback:
                await on_observation_callback(initial_obs)

        # Bounded scroll loop
        scroll_count = 0
        consecutive_unchanged = 0
        max_unchanged = consecutive_unchanged_threshold
        last_doc_height = initial_obs.get("document_height") or 0 if initial_obs else 0
        last_units_count = len(initial_obs.get("content_units") or []) if initial_obs else 0

        while scroll_count < max_scrolls:
            scroll_count += 1
            logger.info(f"Job {self.job_id}: Scroll step {scroll_count}/{max_scrolls}")

            scroll_res = await self.scroll(direction="down", distance=scroll_distance)
            if not scroll_res.success:
                logger.info(f"Job {self.job_id}: Scroll command returned unsuccessful, ending scroll loop. Reason: scroll_failed")
                break

            # Settle delay grows with consecutive unchanged attempts (1s, 2s, 3s)
            current_settle_delay = settle_delay + (consecutive_unchanged * 1.0)
            await asyncio.sleep(current_settle_delay)

            # Wait for page readiness / loading completion
            try:
                await self.wait_for_ready()
            except Exception:
                pass

            obs = await self.read_page()
            if not obs:
                logger.info(f"Job {self.job_id}: Empty observation returned on scroll {scroll_count}. Halting scroll loop. Reason: empty_observation")
                break

            text = obs.get("visible_text") or ""
            c_hash = self.compute_content_hash(text)
            curr_doc_height = obs.get("document_height") or 0
            curr_units_count = len(obs.get("content_units") or [])

            # Check if meaningful new content or structure appeared
            has_new_text = c_hash not in seen_hashes
            has_height_growth = curr_doc_height > last_doc_height and curr_doc_height > 0
            has_new_units = curr_units_count > last_units_count and curr_units_count > 0

            if has_new_text or has_height_growth or has_new_units:
                consecutive_unchanged = 0
                seen_hashes.add(c_hash)
                obs["content_hash"] = c_hash
                last_doc_height = max(last_doc_height, curr_doc_height)
                last_units_count = max(last_units_count, curr_units_count)
                observations.append(obs)
                if on_observation_callback:
                    await on_observation_callback(obs)
            else:
                consecutive_unchanged += 1
                logger.info(
                    f"Job {self.job_id}: No new content detected on scroll {scroll_count} "
                    f"(consecutive attempt {consecutive_unchanged}/{max_unchanged})."
                )
                if consecutive_unchanged >= max_unchanged:
                    logger.info(
                        f"Job {self.job_id}: Halting scroll loop after {consecutive_unchanged} "
                        f"consecutive unchanged reads at scroll {scroll_count}/{max_scrolls}. Reason: page_content_exhausted"
                    )
                    break

        return observations
