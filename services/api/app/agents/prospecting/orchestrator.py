import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared_types.crm import LeadType, SignalType
from packages.shared_types.outreach import DraftStatus, OutreachChannel
from packages.shared_types.prospecting import (
    CandidateStatus,
    ProspectingJobEndReason,
    ProspectingJobStatus,
    ProspectingSourceType,
)
from services.api.app.agents.browser.gateway import (
    BrowserGatewayManager,
    SessionNotConnectedException,
    browser_gateway,
)
from services.api.app.agents.prospecting.command_driver import BrowserCommandDriver
from services.api.app.agents.prospecting.extractor import BusinessExtractor
from services.api.app.agents.prospecting.sources.base import DiscoveredCandidateItem
from services.api.app.agents.prospecting.sources.factory import get_source_adapter
from services.api.app.agents.research.validators import validate_and_sanitize_target_url
from services.api.app.agents.signals.engine import SignalDetectionEngine
from services.api.app.agents.signals.country_detector import CountryDetectionEngine
from services.api.app.models.prospecting import (
    ProspectCandidate,
    ProspectObservation,
    ProspectingJob,
)
from services.api.app.repositories.crm import LeadRepository
from services.api.app.repositories.prospecting import (
    ProspectCandidateRepository,
    ProspectObservationRepository,
    ProspectingJobRepository,
)
from services.api.app.schemas.crm import LeadCreate, LeadSignalCreate
from services.api.app.services.crm_service import DuplicateEntityException, LeadService
from services.api.app.services.normalization import (
    is_disallowed_business_domain,
    is_platform_owned_domain,
    normalize_domain,
    normalize_profile_url,
)
from services.api.app.services.event_dispatcher import EventDispatcher
from services.api.app.services.outreach_service import OutreachService
from services.api.app.services.research_service import ResearchService

logger = logging.getLogger("techverse.agent.prospecting.orchestrator")


class ProspectingOrchestrator:
    """
    Central autonomous prospecting orchestrator executing bounded, user-authorized
    discovery, research, qualification, CRM persistence, and evidence-grounded outreach drafting.
    Halts strictly at READY_FOR_APPROVAL.
    """

    def __init__(
        self,
        session: AsyncSession,
        gateway: Optional[BrowserGatewayManager] = None,
    ):
        self.session = session
        self.gateway = gateway or browser_gateway
        self.job_repo = ProspectingJobRepository(session)
        self.candidate_repo = ProspectCandidateRepository(session)
        self.observation_repo = ProspectObservationRepository(session)
        self.lead_service = LeadService(session)
        self.research_service = ResearchService(session)
        self.outreach_service = OutreachService(session)

    async def execute_job(
        self,
        job_id: uuid.UUID,
        organization_id: uuid.UUID,
        override_session_id: Optional[uuid.UUID] = None,
    ) -> ProspectingJob:
        """
        Execute or resume an autonomous prospecting job with strict safety bounds.
        """
        job = await self.job_repo.get_by_id(job_id, organization_id)
        if not job:
            raise ValueError(f"Job {job_id} not found for organization {organization_id}")

        if job.status in (ProspectingJobStatus.COMPLETED.value, ProspectingJobStatus.CANCELLED.value):
            logger.info(f"Job {job_id} is already in terminal state {job.status}. Skipping execution.")
            return job

        session_id = override_session_id or job.session_id
        if not session_id:
            job = await self.job_repo.update_status(
                job_id,
                organization_id,
                ProspectingJobStatus.WAITING_FOR_USER,
                failure_reason="No browser extension session connected to this job. Pair or select an active browser.",
            )
            await self.session.commit()
            return job

        job.session_id = session_id

        # Verify browser extension connection
        if not self.gateway.is_connected(session_id):
            logger.warning(f"Browser session {session_id} is not connected for job {job_id}")
            job = await self.job_repo.update_status(
                job_id,
                organization_id,
                ProspectingJobStatus.WAITING_FOR_USER,
                end_reason=ProspectingJobEndReason.BROWSER_DISCONNECTED,
                failure_reason="Browser extension is disconnected. Reconnect Chrome extension to resume.",
            )
            await self.session.commit()
            await EventDispatcher.dispatch(
                event_type="browser.disconnected",
                data={"session_id": str(session_id), "job_id": str(job_id)},
                organization_id=organization_id,
            )
            return job

        # Transition to RUNNING
        job = await self.job_repo.update_status(job_id, organization_id, ProspectingJobStatus.RUNNING)
        await self.session.commit()

        await EventDispatcher.dispatch(
            event_type="AGENT_STARTED",
            data={
                "job_id": str(job.id),
                "session_id": str(session_id),
                "source": job.source,
                "query": job.query,
                "max_candidates": job.max_candidates,
            },
            organization_id=organization_id,
            job_id=job.id,
            session_id=session_id,
        )
        await EventDispatcher.dispatch(
            event_type="prospecting.job.started",
            data={
                "job_id": str(job.id),
                "source": job.source,
                "max_candidates": job.max_candidates,
            },
            organization_id=organization_id,
            job_id=job.id,
            session_id=session_id,
        )

        driver = BrowserCommandDriver(
            session_id=session_id,
            org_id=organization_id,
            job_id=job_id,
            gateway=self.gateway,
        )
        source_adapter = get_source_adapter(job.source)
        
        from services.api.app.repositories.prospecting import ProspectingProfileRepository
        profile_repo = ProspectingProfileRepository(self.session)
        profile = await profile_repo.get_or_create(organization_id)

        if hasattr(source_adapter, "get_entry_urls"):
            entry_urls = source_adapter.get_entry_urls(job.query, profile=profile)
        else:
            initial_url = source_adapter.get_initial_url(job.query)
            entry_urls = [initial_url] if initial_url else []

        clean_entry_urls = []
        for u in entry_urls:
            valid_u = validate_and_sanitize_target_url(u)
            if valid_u and valid_u not in clean_entry_urls:
                clean_entry_urls.append(valid_u)
        if not clean_entry_urls and entry_urls:
            clean_entry_urls = entry_urls

        # Budget counters
        start_time = time.time()
        pages_visited = job.statistics.get("pages_visited", 0)
        scrolls_performed = job.statistics.get("scrolls_performed", 0)
        candidates_found = job.statistics.get("candidates_found", 0)
        candidates_qualified = job.statistics.get("candidates_qualified", 0)
        candidates_disqualified = job.statistics.get("candidates_disqualified", 0)
        leads_created = job.statistics.get("leads_created", 0)
        outreach_drafted = job.statistics.get("outreach_drafted", 0)

        meta = job.metadata_json or {}
        saved_visited = meta.get("visited_urls", [])
        saved_frontier = meta.get("frontier", [])

        visited_urls = set(saved_visited)
        if saved_frontier:
            urls_to_visit = [u for u in saved_frontier if u not in visited_urls]
            if not urls_to_visit:
                urls_to_visit = [u for u in clean_entry_urls if u not in visited_urls]
        else:
            urls_to_visit = [u for u in clean_entry_urls if u not in visited_urls]

        loop_end_reason: Optional[ProspectingJobEndReason] = None

        try:
            while urls_to_visit and candidates_qualified < job.max_candidates:
                # Cooperative pause / cancellation check
                from services.api.app.agents.prospecting.worker import prospecting_worker

                if prospecting_worker.is_pause_requested(job_id):
                    logger.info(f"Job {job_id}: Cooperative pause acknowledged.")
                    prospecting_worker.clear_flags(job_id)
                    chk_meta = dict(job.metadata_json or {})
                    chk_meta["visited_urls"] = list(visited_urls)
                    chk_meta["frontier"] = list(urls_to_visit)
                    chk_meta["checkpoint_at"] = datetime.now(timezone.utc).isoformat()
                    job.metadata_json = chk_meta
                    job = await self.job_repo.update_status(
                        job_id,
                        organization_id,
                        ProspectingJobStatus.PAUSED,
                    )
                    await self.session.commit()
                    return job

                if prospecting_worker.is_cancel_requested(job_id):
                    logger.info(f"Job {job_id}: Cooperative cancellation acknowledged.")
                    prospecting_worker.clear_flags(job_id)
                    job = await self.job_repo.update_status(
                        job_id,
                        organization_id,
                        ProspectingJobStatus.CANCELLED,
                        end_reason=ProspectingJobEndReason.CANCELLED,
                        failure_reason="Job cancelled by operator",
                    )
                    await self.session.commit()
                    return job

                # 1. Budget checks
                elapsed = time.time() - start_time
                if job.max_time_seconds and elapsed > job.max_time_seconds:
                    logger.info(f"Job {job_id}: Reached time budget ({job.max_time_seconds}s).")
                    loop_end_reason = ProspectingJobEndReason.BUDGET_TIME if candidates_qualified > 0 else ProspectingJobEndReason.NO_QUALIFIED_FOUND
                    break

                if job.max_pages and pages_visited >= job.max_pages:
                    logger.info(f"Job {job_id}: Reached max pages budget ({job.max_pages}).")
                    loop_end_reason = ProspectingJobEndReason.BUDGET_PAGES if candidates_qualified > 0 else ProspectingJobEndReason.NO_QUALIFIED_FOUND
                    break

                current_url = urls_to_visit.pop(0)
                if current_url in visited_urls:
                    continue
                visited_urls.add(current_url)

                # Check connection before each navigation
                if not driver.is_connected():
                    logger.warning(f"Browser disconnected mid-job for job {job_id}")
                    chk_meta = dict(job.metadata_json or {})
                    chk_meta["visited_urls"] = list(visited_urls)
                    chk_meta["frontier"] = [current_url] + list(urls_to_visit)
                    job.metadata_json = chk_meta
                    job = await self.job_repo.update_status(
                        job_id,
                        organization_id,
                        ProspectingJobStatus.WAITING_FOR_USER,
                        end_reason=ProspectingJobEndReason.BROWSER_DISCONNECTED,
                        failure_reason="Browser extension disconnected during workflow. Reconnect to resume.",
                    )
                    await self.session.commit()
                    return job

                # 2. Open Page
                nav_res = await driver.open_page(current_url)
                pages_visited += 1

                await EventDispatcher.dispatch(
                    event_type="PAGE_OPENED",
                    data={
                        "job_id": str(job.id),
                        "session_id": str(session_id),
                        "url": current_url,
                        "pages_visited": pages_visited,
                    },
                    organization_id=organization_id,
                    job_id=job.id,
                    session_id=session_id,
                )

                if not nav_res.success:
                    if nav_res.status.value == "BLOCKED":
                        logger.warning(f"Job {job_id}: Page navigation blocked: {nav_res.error}")
                        chk_meta = dict(job.metadata_json or {})
                        chk_meta["visited_urls"] = list(visited_urls)
                        chk_meta["frontier"] = list(urls_to_visit)
                        job.metadata_json = chk_meta
                        job = await self.job_repo.update_status(
                            job_id,
                            organization_id,
                            ProspectingJobStatus.BLOCKED,
                            end_reason=ProspectingJobEndReason.BLOCKED,
                            failure_reason=f"Navigation blocked: {nav_res.error}",
                        )
                        await self.session.commit()
                        await EventDispatcher.dispatch(
                            event_type="AGENT_BLOCKED",
                            data={"job_id": str(job_id), "session_id": str(session_id), "reason": nav_res.error, "url": current_url, "end_reason": "BLOCKED"},
                            organization_id=organization_id,
                            job_id=job.id,
                            session_id=session_id,
                        )
                        return job
                    continue

                await driver.wait_for_ready()

                # 2b. Adaptive Search Interaction
                # If page is a search portal / home or query specified, search interactively
                is_search_portal = "/search" in current_url or "search?" in current_url or source_adapter.source_type == ProspectingSourceType.WEB_SEARCH
                should_search = bool(job.query) or is_search_portal
                if should_search:
                    search_q = job.query
                    if not search_q and profile and getattr(profile, "ideal_customer_keywords", None):
                        search_q = profile.ideal_customer_keywords[0]
                    if not search_q and is_search_portal:
                        search_q = "looking for a developer"

                    if search_q:
                        try:
                            discovery = await driver.find_search_input()
                            if discovery.get("found"):
                                logger.info(f"Job {job_id}: Discovered search input ({discovery.get('selector')}). Executing search for '{search_q}'")
                                search_res = await driver.interactive_search(query=search_q, search_input_selector=discovery.get("selector"))
                                if search_res.get("success"):
                                    await EventDispatcher.dispatch(
                                        event_type="SEARCH_SUBMITTED",
                                        data={
                                            "job_id": str(job.id),
                                            "session_id": str(session_id),
                                            "query": search_q,
                                            "selector": discovery.get("selector"),
                                            "url": current_url,
                                        },
                                        organization_id=organization_id,
                                        job_id=job.id,
                                        session_id=session_id,
                                    )
                            else:
                                logger.info(f"Job {job_id}: SEARCH_INPUT_NOT_FOUND on {current_url}. Falling back to direct page reading.")
                        except Exception as search_err:
                            logger.warning(f"Job {job_id}: Search interaction skipped or failed: {search_err}")

                # 3. Read Page & Check Security Barrier
                read_res = await driver.read_page()
                if not read_res:
                    continue

                await EventDispatcher.dispatch(
                    event_type="PAGE_READ",
                    data={
                        "job_id": str(job.id),
                        "session_id": str(session_id),
                        "url": current_url,
                        "content_units": len(read_res.get("content_units") or []),
                    },
                    organization_id=organization_id,
                    job_id=job.id,
                    session_id=session_id,
                )

                challenge = source_adapter.detect_security_challenge(read_res)
                if challenge.is_blocked:
                    logger.warning(f"Job {job_id}: Security challenge encountered: {challenge.reason}")
                    chk_meta = dict(job.metadata_json or {})
                    chk_meta["visited_urls"] = list(visited_urls)
                    chk_meta["frontier"] = list(urls_to_visit)
                    job.metadata_json = chk_meta
                    job = await self.job_repo.update_status(
                        job_id,
                        organization_id,
                        ProspectingJobStatus.BLOCKED,
                        end_reason=ProspectingJobEndReason.BLOCKED,
                        failure_reason=challenge.reason or "Security barrier or CAPTCHA detected",
                    )
                    await self.session.commit()
                    await EventDispatcher.dispatch(
                        event_type="AGENT_BLOCKED",
                        data={"job_id": str(job_id), "session_id": str(session_id), "reason": challenge.reason, "url": current_url, "end_reason": "BLOCKED"},
                        organization_id=organization_id,
                        job_id=job.id,
                        session_id=session_id,
                    )
                    await EventDispatcher.dispatch(
                        event_type="browser.security.challenge",
                        data={"job_id": str(job_id), "reason": challenge.reason, "url": current_url},
                        organization_id=organization_id,
                        job_id=job.id,
                        session_id=session_id,
                    )
                    return job

                # 4. Controlled Scrolling & Reading
                async def _on_scroll_step(step_obs: Dict[str, Any]):
                    await EventDispatcher.dispatch(
                        event_type="PAGE_SCROLLED",
                        data={
                            "job_id": str(job.id),
                            "session_id": str(session_id),
                            "url": step_obs.get("url") or current_url,
                            "content_units": len(step_obs.get("content_units") or []),
                        },
                        organization_id=organization_id,
                        job_id=job.id,
                        session_id=session_id,
                    )

                observations = await driver.controlled_scroll_and_read(
                    max_scrolls=job.max_scrolls,
                    initial_observation=read_res,
                    on_observation_callback=_on_scroll_step,
                )
                scrolls_performed += len(observations)

                # Persist durable observations
                for obs in observations:
                    text = obs.get("visible_text") or ""
                    db_obs = ProspectObservation(
                        job_id=job.id,
                        session_id=session_id,
                        organization_id=organization_id,
                        url=obs.get("url") or current_url,
                        platform=job.source,
                        page_title=obs.get("page_title"),
                        visible_text=text[:5000] if text else None,
                        headings=obs.get("headings"),
                        links=obs.get("links"),
                        content_hash=obs.get("content_hash"),
                        metadata_json=obs,
                    )
                    await self.observation_repo.create(db_obs)

                # 5. Candidate Discovery across observations
                discovered_items: List[DiscoveredCandidateItem] = []
                for obs in observations:
                    items = source_adapter.discover_candidates(obs, query=job.query)
                    discovered_items.extend(items)

                if discovered_items:
                    await EventDispatcher.dispatch(
                        event_type="CONTENT_DISCOVERED",
                        data={
                            "job_id": str(job.id),
                            "session_id": str(session_id),
                            "count": len(discovered_items),
                            "url": current_url,
                        },
                        organization_id=organization_id,
                        job_id=job.id,
                        session_id=session_id,
                    )

                for item in discovered_items:
                    # 0. Safely initialize all per-candidate variables to prevent cross-candidate leakage
                    lead = None
                    signals = []
                    has_intent = False
                    urgency_res = None
                    created_cand = None
                    biz_info = None
                    drafts = []
                    website_pages_data = None
                    target_web_url = None

                    try:
                        dedup_key = source_adapter.build_dedup_key(item)

                        # Deduplication check within job
                        existing_cand = await self.candidate_repo.get_by_dedup_key(job.id, dedup_key)
                        if existing_cand:
                            continue

                        # Global duplicate check across org
                        global_dup = await self.candidate_repo.find_global_duplicate(organization_id, dedup_key)
                        if global_dup and global_dup.linked_lead_id:
                            # Record as DUPLICATE and skip
                            cand_model = ProspectCandidate(
                                job_id=job.id,
                                organization_id=organization_id,
                                source=job.source,
                                source_url=item.source_url,
                                canonical_url=item.canonical_url,
                                platform=item.platform,
                                username_or_handle=item.username_or_handle,
                                company_name=item.company_name,
                                domain=item.domain,
                                discovery_evidence=item.evidence,
                                status=CandidateStatus.DUPLICATE.value,
                                confidence=item.confidence,
                                dedup_key=dedup_key,
                                linked_lead_id=global_dup.linked_lead_id,
                            )
                            await self.candidate_repo.create(cand_model)
                            await EventDispatcher.dispatch(
                                event_type="prospect.deduplicated",
                                data={"job_id": str(job.id), "dedup_key": dedup_key},
                                organization_id=organization_id,
                                job_id=job.id,
                                session_id=session_id,
                            )
                            continue

                        # Insert new candidate (DISCOVERED)
                        candidates_found += 1
                        cand_model = ProspectCandidate(
                            job_id=job.id,
                            organization_id=organization_id,
                            source=job.source,
                            source_url=item.source_url,
                            canonical_url=item.canonical_url,
                            platform=item.platform,
                            username_or_handle=item.username_or_handle,
                            company_name=item.company_name,
                            domain=item.domain,
                            business_category=item.business_category,
                            discovery_evidence=item.evidence,
                            status=CandidateStatus.DISCOVERED.value,
                            confidence=item.confidence,
                            dedup_key=dedup_key,
                        )
                        created_cand = await self.candidate_repo.create(cand_model)
                        await EventDispatcher.dispatch(
                            event_type="CANDIDATE_CREATED",
                            data={
                                "job_id": str(job.id),
                                "session_id": str(session_id),
                                "candidate_id": str(created_cand.id),
                                "name": created_cand.company_name,
                                "author": created_cand.username_or_handle,
                                "platform": created_cand.platform,
                                "source_url": created_cand.source_url,
                            },
                            organization_id=organization_id,
                            job_id=job.id,
                            session_id=session_id,
                        )
                        await EventDispatcher.dispatch(
                            event_type="prospect.discovered",
                            data={
                                "job_id": str(job.id),
                                "candidate_id": str(created_cand.id),
                                "name": created_cand.company_name,
                                "platform": created_cand.platform,
                            },
                            organization_id=organization_id,
                            job_id=job.id,
                            session_id=session_id,
                        )

                        # 6. Extract Truthful Business Details
                        primary_obs = observations[0] if observations else {}
                        biz_info = BusinessExtractor.extract_business(
                            primary_obs,
                            profile_url=created_cand.source_url,
                            recipient_handle=created_cand.username_or_handle,
                        )
                        if created_cand.domain and is_disallowed_business_domain(created_cand.domain):
                            created_cand.domain = None
                        if biz_info.domain and is_disallowed_business_domain(biz_info.domain):
                            biz_info.domain = None
                        if biz_info.company_name and not created_cand.company_name:
                            created_cand.company_name = biz_info.company_name
                        if biz_info.domain and not created_cand.domain:
                            created_cand.domain = biz_info.domain
                        if biz_info.business_category:
                            created_cand.business_category = biz_info.business_category

                        # 7. Signal, Intent & Urgency Detection (per Candidate)
                        candidate_text = f"{created_cand.discovery_evidence or ''} {created_cand.company_name or ''}".strip()
                        if len(discovered_items) <= 1:
                            primary_obs_text = " ".join([o.get("visible_text") or "" for o in observations])
                            eval_text = f"{candidate_text} {primary_obs_text}".strip()
                        else:
                            eval_text = candidate_text

                        # 7a. Anti-false positive check
                        if SignalDetectionEngine.check_false_positive(eval_text):
                            disqual_reason = SignalDetectionEngine.classify_disqualification(eval_text) or "Competitor/Student/Job Seeker indicator matched"
                            logger.info(f"Candidate {created_cand.id} ({created_cand.company_name}) disqualified: {disqual_reason}")
                            meta = dict(created_cand.metadata_json or {})
                            meta["disqualification_reason"] = disqual_reason
                            created_cand.metadata_json = meta
                            await self.candidate_repo.update_status(
                                created_cand.id,
                                organization_id,
                                CandidateStatus.DISQUALIFIED,
                            )
                            candidates_disqualified += 1
                            await EventDispatcher.dispatch(
                                event_type="prospect.disqualified",
                                data={
                                    "candidate_id": str(created_cand.id),
                                    "reason": disqual_reason,
                                    "evidence": created_cand.discovery_evidence,
                                },
                                organization_id=organization_id,
                                job_id=job.id,
                                session_id=session_id,
                            )
                            await self.session.commit()
                            continue

                        # 7b. Intent detection
                        signals = SignalDetectionEngine.detect_signals(
                            text=eval_text,
                            source_url=created_cand.source_url,
                        )
                        has_intent = SignalDetectionEngine.has_explicit_intent(signals)

                        # 7c. Deterministic Urgency & Country Detection
                        urgency_res = SignalDetectionEngine.evaluate_urgency(eval_text)
                        country_res = CountryDetectionEngine.evaluate(
                            text=eval_text,
                            domain=created_cand.domain,
                            source_url=created_cand.source_url,
                            declared_location=created_cand.location,
                        )

                        # Record verified country evidence
                        if country_res.country:
                            created_cand.location = country_res.city_or_state or country_res.country

                        meta = dict(created_cand.metadata_json or {})
                        meta["country"] = country_res.country
                        meta["country_confidence"] = country_res.confidence
                        meta["country_evidence"] = country_res.evidence

                        # 7d. Three-tier qualification: QUALIFIED vs REVIEW_REQUIRED vs DISQUALIFIED
                        has_biz_opportunity = bool(
                            (created_cand.domain and not is_disallowed_business_domain(created_cand.domain))
                            or (biz_info and biz_info.domain and not is_disallowed_business_domain(biz_info.domain))
                            or len(signals) > 0
                        )

                        # A candidate requires an attributable source URL and attributable identity
                        is_attributable = bool(
                            (created_cand.company_name or created_cand.username_or_handle)
                            and (created_cand.company_name or "").lower() not in ("discovered prospect", "linkedin member", "none")
                            and created_cand.source_url
                            and not any(g in (created_cand.source_url or "") for g in ("/search", "/feed", "example.com"))
                        )

                        if has_intent and is_attributable:
                            cand_status = CandidateStatus.QUALIFIED
                            cand_conf = max(created_cand.confidence, 0.85)
                            meta["qualification_category"] = "QUALIFIED"
                            meta["qualification_reasons"] = "Verified explicit buying intent matched with attributable source."
                        elif has_biz_opportunity and (signals or (biz_info and biz_info.company_name)):
                            cand_status = CandidateStatus.REVIEW_REQUIRED
                            cand_conf = 0.65
                            meta["qualification_category"] = "REVIEW_REQUIRED"
                            meta["qualification_reasons"] = "Potentially relevant business with service opportunity; manual review recommended to confirm buying timeframe."
                        else:
                            disqual_reason = "No commercial buying intent detected (generic business existence or ambiguous inquiry without service request)"
                            logger.info(f"Candidate {created_cand.id} ({created_cand.company_name}) disqualified: {disqual_reason}")
                            meta["disqualification_reason"] = disqual_reason
                            meta["urgency"] = urgency_res.level.value
                            meta["urgency_reason"] = urgency_res.reason
                            meta["qualification_category"] = "DISQUALIFIED"
                            created_cand.metadata_json = meta
                            await self.candidate_repo.update_status(
                                created_cand.id,
                                organization_id,
                                CandidateStatus.DISQUALIFIED,
                            )
                            candidates_disqualified += 1
                            await EventDispatcher.dispatch(
                                event_type="prospect.disqualified",
                                data={
                                    "candidate_id": str(created_cand.id),
                                    "reason": disqual_reason,
                                    "evidence": created_cand.discovery_evidence,
                                },
                                organization_id=organization_id,
                                job_id=job.id,
                                session_id=session_id,
                            )
                            await self.session.commit()
                            continue

                        # 8. Mark Candidate Status & Persist Urgency / Metadata
                        meta["urgency"] = urgency_res.level.value
                        meta["urgency_score"] = urgency_res.score
                        meta["urgency_reason"] = urgency_res.reason
                        meta["urgency_evidence"] = urgency_res.evidence
                        created_cand.metadata_json = meta

                        await self.candidate_repo.update_status(
                            created_cand.id,
                            organization_id,
                            cand_status,
                            confidence=cand_conf,
                        )
                        if cand_status == CandidateStatus.QUALIFIED:
                            candidates_qualified += 1

                        # 9. Real Website Research (when public website available)
                        if created_cand.domain:
                            target_web_url = f"https://{created_cand.domain}"
                        elif biz_info.domain:
                            target_web_url = f"https://{biz_info.domain}"

                        if target_web_url and driver.is_connected():
                            try:
                                logger.info(f"Researching website for candidate {created_cand.id}: {target_web_url}")
                                await EventDispatcher.dispatch(
                                    event_type="WEBSITE_RESEARCH_STARTED",
                                    data={
                                        "job_id": str(job.id),
                                        "session_id": str(session_id),
                                        "url": target_web_url,
                                        "candidate_id": str(created_cand.id),
                                    },
                                    organization_id=organization_id,
                                    job_id=job.id,
                                    session_id=session_id,
                                )
                                web_res = await driver.open_page(target_web_url)
                                if web_res.success:
                                    await driver.wait_for_ready()
                                    web_obs = await driver.read_page()
                                    if web_obs and web_obs.get("visible_text"):
                                        website_pages_data = [
                                            {
                                                "url": target_web_url,
                                                "page_type": "HOMEPAGE",
                                                "visible_text": web_obs.get("visible_text"),
                                                "title": web_obs.get("title"),
                                            }
                                        ]
                                await EventDispatcher.dispatch(
                                    event_type="WEBSITE_RESEARCH_COMPLETED",
                                    data={
                                        "job_id": str(job.id),
                                        "session_id": str(session_id),
                                        "url": target_web_url,
                                        "candidate_id": str(created_cand.id),
                                        "status": "COMPLETED" if web_res.success else "FAILED",
                                    },
                                    organization_id=organization_id,
                                    job_id=job.id,
                                    session_id=session_id,
                                )
                            except Exception as e:
                                logger.info(f"Website research navigation skipped or failed: {e}")

                        # 10. Create CRM Lead strictly for QUALIFIED prospects
                        if cand_status != CandidateStatus.QUALIFIED:
                            logger.info(
                                f"Candidate {created_cand.id} ({created_cand.company_name or created_cand.username_or_handle}) "
                                f"status is {cand_status.value}; keeping as REVIEW_REQUIRED without CRM conversion."
                            )
                            await self.session.commit()
                            continue

                        lead_title = created_cand.company_name or created_cand.username_or_handle
                        if not lead_title or lead_title.lower() in ("discovered prospect", "linkedin member", "none"):
                            logger.info(f"Candidate {created_cand.id} lacks attributable identity; skipping CRM lead creation.")
                            await self.session.commit()
                            continue

                        clean_profile = normalize_profile_url(created_cand.source_url)
                        matched_service = job.target_service
                        service_inferred = False
                        service_inference_source = "JOB_TARGET"

                        if not matched_service:
                            service_inferred = True
                            if signals:
                                primary_sig = signals[0].signal_type
                                service_inference_source = f"SIGNAL:{primary_sig.value if hasattr(primary_sig, 'value') else primary_sig}"
                                if primary_sig == SignalType.WEBSITE_REQUEST:
                                    matched_service = "Business Website"
                                elif primary_sig == SignalType.WEBSITE_OUTDATED:
                                    matched_service = "Website Redesign"
                                elif primary_sig == SignalType.APP_DEVELOPMENT_REQUEST:
                                    matched_service = "Mobile App Development"
                                elif primary_sig == SignalType.AI_AUTOMATION_REQUEST:
                                    matched_service = "AI Automation & Workflows"
                                elif primary_sig == SignalType.ECOMMERCE_OPPORTUNITY:
                                    matched_service = "Ecommerce Storefront"
                                elif primary_sig == SignalType.REQUEST_FOR_SERVICE:
                                    matched_service = "Full-Service Digital Agency"
                                else:
                                    matched_service = "General Digital & Technology Services"
                            else:
                                matched_service = "General Digital & Technology Services"
                                service_inference_source = "GENERIC_FALLBACK"

                        if not matched_service:
                            matched_service = "General Digital & Technology Services"
                            service_inferred = True
                            service_inference_source = "GENERIC_FALLBACK"

                        # Record inference metadata on candidate
                        cand_meta = dict(created_cand.metadata_json or {})
                        cand_meta["service_inferred"] = service_inferred
                        cand_meta["service_inference_source"] = service_inference_source
                        cand_meta["recommended_service"] = matched_service
                        created_cand.metadata_json = cand_meta

                        try:
                            lead = await self.lead_service.create_lead(
                                LeadCreate(
                                    organization_id=organization_id,
                                    title=lead_title,
                                    summary=f"Autonomous discovery via {job.source}: {created_cand.discovery_evidence}",
                                    lead_type=LeadType.COMPANY,
                                    source_url=created_cand.source_url,
                                    profile_url=clean_profile,
                                    intent_score=urgency_res.score if urgency_res else 50,
                                    overall_score=urgency_res.score if urgency_res else 50,
                                    recommended_service=matched_service,
                                )
                            )
                        except DuplicateEntityException as dup_err:
                            if dup_err.matched_entity_id:
                                lead = await self.lead_service.get_lead(organization_id, dup_err.matched_entity_id)
                        except Exception as err:
                            logger.warning(f"Error creating lead: {err}")

                        if lead:
                            leads_created += 1
                            created_cand.linked_lead_id = lead.id
                            await self.candidate_repo.update_status(
                                created_cand.id,
                                organization_id,
                                CandidateStatus.CONVERTED_TO_LEAD,
                                linked_lead_id=lead.id,
                            )

                            await EventDispatcher.dispatch(
                                event_type="LEAD_CREATED",
                                data={
                                    "job_id": str(job.id),
                                    "session_id": str(session_id),
                                    "lead_id": str(lead.id),
                                    "candidate_id": str(created_cand.id),
                                    "title": lead_title,
                                },
                                organization_id=organization_id,
                                lead_id=lead.id,
                                job_id=job.id,
                                session_id=session_id,
                            )

                            # Add detected signals to CRM lead
                            for sig in signals:
                                try:
                                    await self.lead_service.add_signal(
                                        org_id=organization_id,
                                        data=LeadSignalCreate(
                                            lead_id=lead.id,
                                            signal_type=sig.signal_type,
                                            confidence=sig.confidence,
                                            evidence=sig.evidence,
                                            source_url=sig.source_url or current_url,
                                        ),
                                    )
                                except Exception:
                                    pass

                            # Real Lead Scoring Service execution (no hardcoded score defaults)
                            try:
                                _, qualification = await self.lead_service.analyze_signals(
                                    org_id=organization_id,
                                    lead_id=lead.id,
                                    text=eval_text,
                                    source_url=current_url,
                                )
                                # Reload lead to obtain persisted scored state
                                lead = await self.lead_service.get_lead(organization_id, lead.id)
                            except Exception as e:
                                logger.warning(f"Error analyzing signals for lead {lead.id}: {e}")

                            # Execute website research audit persistence if website was visited
                            if target_web_url and website_pages_data:
                                try:
                                    await self.research_service.execute_lead_website_research(
                                        lead_id=lead.id,
                                        org_id=organization_id,
                                        override_url=target_web_url,
                                        pages_data=website_pages_data,
                                    )
                                except Exception as e:
                                    logger.warning(f"Error persisting website research for lead {lead.id}: {e}")

                            # 11. Generate Evidence-Grounded Outreach Draft (READY_FOR_APPROVAL)
                            channel = OutreachChannel.INSTAGRAM_DM
                            if job.source == ProspectingSourceType.INSTAGRAM.value:
                                channel = OutreachChannel.INSTAGRAM_DM
                            elif job.source == ProspectingSourceType.REDDIT.value:
                                channel = OutreachChannel.REDDIT_REPLY
                            elif job.source == ProspectingSourceType.THREADS.value:
                                channel = OutreachChannel.INSTAGRAM_DM
                            else:
                                channel = OutreachChannel.EMAIL

                            try:
                                drafts = await self.outreach_service.generate_outreach(
                                    organization_id=organization_id,
                                    lead_id=lead.id,
                                    channel=channel,
                                    variant_count=1,
                                )
                                if drafts:
                                    outreach_drafted += len(drafts)
                                    await EventDispatcher.dispatch(
                                        event_type="outreach.ready_for_approval",
                                        data={"job_id": str(job.id), "lead_id": str(lead.id), "draft_count": len(drafts)},
                                        organization_id=organization_id,
                                        job_id=job.id,
                                        session_id=session_id,
                                    )
                            except Exception as e:
                                logger.info(f"Outreach generation skipped or duplicate: {e}")

                            # Derive approval status strictly from actual draft records
                            has_ready_draft = any(getattr(d, "status", None) == DraftStatus.READY_FOR_APPROVAL.value for d in drafts)
                            approval_status = "READY_FOR_APPROVAL" if has_ready_draft else "QUALIFIED"

                            # Broadcast CANDIDATE_QUALIFIED with truthful scoring
                            await EventDispatcher.dispatch(
                                event_type="CANDIDATE_QUALIFIED",
                                data={
                                    "job_id": str(job.id),
                                    "session_id": str(session_id),
                                    "candidate_id": str(created_cand.id),
                                    "author": created_cand.username_or_handle,
                                    "intent_score": getattr(lead, "intent_score", None),
                                    "urgency": urgency_res.level.value,
                                    "urgency_reason": urgency_res.reason,
                                },
                                organization_id=organization_id,
                                job_id=job.id,
                                session_id=session_id,
                            )

                            # EMIT PROSPECT_DISCOVERED ONLY AFTER QUALIFICATION, REAL SCORING, AND DRAFTING COMPLETE
                            resolved_intent = getattr(lead, "intent_score", None)
                            resolved_overall = getattr(lead, "overall_score", None)
                            lead_created_at = lead.created_at.isoformat() if hasattr(lead, "created_at") and lead.created_at else datetime.now(timezone.utc).isoformat()
                            prospect_event_payload = {
                                "candidate_id": str(created_cand.id),
                                "lead_id": str(lead.id),
                                "platform": created_cand.platform,
                                "author": created_cand.username_or_handle or lead_title,
                                "source_url": created_cand.source_url,
                                "evidence": created_cand.discovery_evidence,
                                "score": resolved_overall,
                                "intent_score": resolved_intent,
                                "urgency": urgency_res.level.value,
                                "urgency_reason": urgency_res.reason,
                                "urgency_evidence": urgency_res.evidence,
                                "service_match": getattr(lead, "recommended_service", None) or matched_service,
                                "website": created_cand.domain or biz_info.domain,
                                "created_at": lead_created_at,
                                "status": approval_status,
                            }
                            await EventDispatcher.dispatch(
                                event_type="PROSPECT_DISCOVERED",
                                data=prospect_event_payload,
                                organization_id=organization_id,
                                lead_id=lead.id,
                                job_id=job.id,
                                session_id=session_id,
                            )

                        # Commit progress per candidate to avoid loss on unexpected restarts
                        await self.session.commit()

                    except Exception as cand_err:
                        logger.error(
                            f"Job {job_id}: Candidate processing error: {cand_err}",
                            exc_info=True,
                        )
                        await self.session.rollback()
                        continue

                # 12. Enqueue Next Frontier URLs from Source Adapter
                try:
                    next_links = source_adapter.next_urls(read_res, job.query)
                    for nxt in next_links:
                        try:
                            clean_nxt = validate_and_sanitize_target_url(nxt)
                            if clean_nxt not in visited_urls and clean_nxt not in urls_to_visit:
                                if len(urls_to_visit) < (job.max_pages - pages_visited):
                                    urls_to_visit.append(clean_nxt)
                        except Exception:
                            continue
                except Exception as nxt_err:
                    logger.warning(f"Job {job_id}: Failed to resolve next frontier URLs: {nxt_err}")

                # 13. Persist progress per page (statistics + visited_urls + frontier)
                chk_meta = dict(job.metadata_json or {})
                chk_meta["visited_urls"] = list(visited_urls)
                chk_meta["frontier"] = list(urls_to_visit)
                chk_meta["pages_visited"] = pages_visited
                chk_meta["checkpoint_at"] = datetime.now(timezone.utc).isoformat()
                job.metadata_json = chk_meta
                await self.job_repo.update_statistics(
                    job_id,
                    organization_id,
                    {
                        "pages_visited": pages_visited,
                        "scrolls_performed": scrolls_performed,
                        "candidates_found": candidates_found,
                        "candidates_qualified": candidates_qualified,
                        "candidates_disqualified": candidates_disqualified,
                        "leads_created": leads_created,
                        "outreach_drafted": outreach_drafted,
                    },
                )
                await self.session.commit()

            # End of main discovery loop -> Determine accurate end_reason
            if candidates_qualified >= job.max_candidates:
                final_end_reason = ProspectingJobEndReason.OBJECTIVE_MET
            elif loop_end_reason is not None:
                final_end_reason = loop_end_reason
            elif not urls_to_visit:
                final_end_reason = (
                    ProspectingJobEndReason.PAGE_EXHAUSTED
                    if candidates_qualified > 0
                    else ProspectingJobEndReason.NO_QUALIFIED_FOUND
                )
            else:
                final_end_reason = (
                    ProspectingJobEndReason.OBJECTIVE_MET
                    if candidates_qualified > 0
                    else ProspectingJobEndReason.NO_QUALIFIED_FOUND
                )

            job = await self.job_repo.update_status(
                job_id,
                organization_id,
                ProspectingJobStatus.COMPLETED,
                end_reason=final_end_reason,
            )
            await self.session.commit()

            await EventDispatcher.dispatch(
                event_type="AGENT_COMPLETED",
                data={
                    "job_id": str(job.id),
                    "session_id": str(session_id),
                    "end_reason": final_end_reason.value,
                    "candidates_qualified": candidates_qualified,
                    "leads_created": leads_created,
                    "outreach_drafted": outreach_drafted,
                },
                organization_id=organization_id,
                job_id=job.id,
                session_id=session_id,
            )
            await EventDispatcher.dispatch(
                event_type="prospecting.job.completed",
                data={
                    "job_id": str(job.id),
                    "end_reason": final_end_reason.value,
                    "candidates_qualified": candidates_qualified,
                    "leads_created": leads_created,
                    "outreach_drafted": outreach_drafted,
                },
                organization_id=organization_id,
                job_id=job.id,
                session_id=session_id,
            )
            return job

        except SessionNotConnectedException:
            logger.warning(f"Session disconnected during job {job_id}")
            job = await self.job_repo.update_status(
                job_id,
                organization_id,
                ProspectingJobStatus.WAITING_FOR_USER,
                end_reason=ProspectingJobEndReason.BROWSER_DISCONNECTED,
                failure_reason="Browser extension disconnected. Reconnect Chrome extension to resume.",
            )
            await self.session.commit()
            return job

        except Exception as e:
            logger.error(f"Error in prospecting job {job_id}: {e}", exc_info=True)
            job = await self.job_repo.update_status(
                job_id,
                organization_id,
                ProspectingJobStatus.FAILED,
                end_reason=ProspectingJobEndReason.FAILED,
                failure_reason=str(e),
            )
            await self.session.commit()
            return job

        finally:
            if driver and driver.is_connected():
                if job and job.status in (
                    ProspectingJobStatus.COMPLETED.value,
                    ProspectingJobStatus.CANCELLED.value,
                    ProspectingJobStatus.FAILED.value,
                ):
                    try:
                        await driver.stop()
                    except Exception:
                        pass
