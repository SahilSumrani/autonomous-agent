import asyncio
import json
import uuid
from typing import Any, Dict, List, Optional, Set
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared_types.prospecting import CandidateStatus, ProspectingJobStatus
from services.api.app.models.crm import Lead
from services.api.app.models.prospecting import ProspectCandidate, ProspectingJob
from services.api.app.agents.prospecting.worker import prospecting_worker
from services.api.app.api.v1.dependencies.auth import AuthenticatedActor, get_authenticated_actor, get_current_org_id
from services.api.app.core.database import get_db
from services.api.app.core.redis import get_redis
from services.api.app.repositories.prospecting import ProspectingProfileRepository
from services.api.app.schemas.prospecting import (
    ProspectCandidateResponse,
    ProspectObservationResponse,
    ProspectingJobCreate,
    ProspectingJobResponse,
    ProspectingProfileRead,
    ProspectingProfileUpdate,
)
from services.api.app.services.event_dispatcher import EventDispatcher
from services.api.app.services.normalization import is_disallowed_business_domain
from services.api.app.services.prospecting_service import (
    JobNotFoundException,
    ProspectingService,
)

router = APIRouter(prefix="/prospecting", tags=["Autonomous Prospecting"])


@router.post(
    "/jobs",
    response_model=ProspectingJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create and optionally start an autonomous prospecting job",
)
async def create_job(
    data: ProspectingJobCreate,
    auto_start: bool = Query(True, description="Immediately queue job in background worker"),
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
) -> ProspectingJobResponse:
    org_id = actor.organization_id

    # If initiated by a browser session: narrowly scope authorization to its specific session
    if actor.actor_type == "BROWSER_SESSION":
        if data.session_id and data.session_id != actor.session_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Browser session {actor.session_id} cannot initiate jobs for different session {data.session_id}",
            )
        data.session_id = actor.session_id

    service = ProspectingService(db)
    job = await service.create_job(org_id, data)

    if auto_start and data.session_id:
        prospecting_worker.start_job_task(job.id, org_id, data.session_id)

    return ProspectingJobResponse.model_validate(job)


@router.get(
    "/jobs",
    response_model=List[ProspectingJobResponse],
    summary="List prospecting jobs for current organization",
)
async def list_jobs(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> List[ProspectingJobResponse]:
    service = ProspectingService(db)
    items, _ = await service.list_jobs(org_id, status=status_filter, limit=limit, offset=offset)
    return [ProspectingJobResponse.model_validate(j) for j in items]


@router.get(
    "/jobs/{job_id}",
    response_model=ProspectingJobResponse,
    summary="Get prospecting job details",
)
async def get_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> ProspectingJobResponse:
    service = ProspectingService(db)
    try:
        job = await service.get_job(org_id, job_id)
        return ProspectingJobResponse.model_validate(job)
    except JobNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/jobs/{job_id}/start",
    response_model=ProspectingJobResponse,
    summary="Start or queue a created prospecting job",
)
async def start_job(
    job_id: uuid.UUID,
    session_id: Optional[uuid.UUID] = Query(None, description="Active browser agent session ID"),
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
) -> ProspectingJobResponse:
    org_id = actor.organization_id
    if actor.actor_type == "BROWSER_SESSION":
        if session_id and session_id != actor.session_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Browser session {actor.session_id} cannot start jobs for different session {session_id}",
            )
        session_id = actor.session_id

    service = ProspectingService(db)
    try:
        job = await service.get_job(org_id, job_id)
        bound_session_id = session_id or job.session_id
        if not bound_session_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A valid connected browser session_id is required to start this job.",
            )

        prospecting_worker.start_job_task(job.id, org_id, bound_session_id)
        return ProspectingJobResponse.model_validate(job)
    except JobNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/jobs/{job_id}/pause",
    response_model=ProspectingJobResponse,
    summary="Pause a running prospecting job",
)
async def pause_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
) -> ProspectingJobResponse:
    org_id = actor.organization_id
    service = ProspectingService(db)
    try:
        job = await service.get_job(org_id, job_id)
        if actor.actor_type == "BROWSER_SESSION" and job.session_id and job.session_id != actor.session_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Browser session cannot control job owned by a different session",
            )
        prospecting_worker.request_pause(job_id)
        job = await service.pause_job(org_id, job_id)
        return ProspectingJobResponse.model_validate(job)
    except JobNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/jobs/{job_id}/resume",
    response_model=ProspectingJobResponse,
    summary="Resume a paused or waiting prospecting job",
)
async def resume_job(
    job_id: uuid.UUID,
    session_id: Optional[uuid.UUID] = Query(None, description="Reconnected browser agent session ID"),
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
) -> ProspectingJobResponse:
    org_id = actor.organization_id
    if actor.actor_type == "BROWSER_SESSION":
        if session_id and session_id != actor.session_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Browser session {actor.session_id} cannot resume jobs for different session {session_id}",
            )
        session_id = actor.session_id

    service = ProspectingService(db)
    try:
        job = await service.resume_job(org_id, job_id)
        bound_session_id = session_id or job.session_id
        if bound_session_id:
            prospecting_worker.start_job_task(job.id, org_id, bound_session_id)
        return ProspectingJobResponse.model_validate(job)
    except JobNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=ProspectingJobResponse,
    summary="Cancel a prospecting job",
)
async def cancel_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
) -> ProspectingJobResponse:
    org_id = actor.organization_id
    service = ProspectingService(db)
    try:
        job = await service.get_job(org_id, job_id)
        if actor.actor_type == "BROWSER_SESSION" and job.session_id and job.session_id != actor.session_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Browser session cannot cancel job owned by a different session",
            )
        prospecting_worker.cancel_job_task(job_id)
        job = await service.cancel_job(org_id, job_id)
        return ProspectingJobResponse.model_validate(job)
    except JobNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/jobs/{job_id}/candidates",
    response_model=List[ProspectCandidateResponse],
    summary="List candidates discovered by this job",
)
async def list_job_candidates(
    job_id: uuid.UUID,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> List[ProspectCandidateResponse]:
    service = ProspectingService(db)
    try:
        cands = await service.list_candidates(org_id, job_id, status=status_filter)
        return [ProspectCandidateResponse.model_validate(c) for c in cands]
    except JobNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/jobs/{job_id}/observations",
    response_model=List[ProspectObservationResponse],
    summary="List content observations recorded during this job",
)
async def list_job_observations(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> List[ProspectObservationResponse]:
    service = ProspectingService(db)
    try:
        obs_list = await service.list_observations(org_id, job_id)
        return [
            ProspectObservationResponse(
                id=o.id,
                job_id=o.job_id,
                candidate_id=o.candidate_id,
                session_id=o.session_id,
                organization_id=o.organization_id,
                url=o.url,
                platform=o.platform,
                page_title=o.page_title,
                visible_text_snippet=(o.visible_text or "")[:200],
                headings=o.headings,
                content_hash=o.content_hash,
                created_at=o.created_at,
            )
            for o in obs_list
        ]
    except JobNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/profile",
    response_model=ProspectingProfileRead,
    summary="Get or initialize organization prospecting profile",
)
async def get_prospecting_profile(
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
) -> ProspectingProfileRead:
    repo = ProspectingProfileRepository(db)
    profile = await repo.get_or_create(actor.organization_id)
    return ProspectingProfileRead.model_validate(profile)


@router.put(
    "/profile",
    response_model=ProspectingProfileRead,
    summary="Update organization prospecting profile",
)
async def update_prospecting_profile(
    data: ProspectingProfileUpdate,
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedActor = Depends(get_authenticated_actor),
) -> ProspectingProfileRead:
    repo = ProspectingProfileRepository(db)
    profile = await repo.update(actor.organization_id, data.model_dump(exclude_unset=True))
    return ProspectingProfileRead.model_validate(profile)


from services.api.app.api.v1.dependencies.auth import authenticate_ws_actor


@router.websocket("/events/ws")
async def prospecting_events_ws(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    org_id: Optional[str] = Query(None),
):
    """
    Real-time WebSocket event stream for dashboard UI.
    Authenticated and scoped strictly to the authenticated organization.
    Prevents cross-tenant event snooping and deduplicates event delivery.
    """
    try:
        actor = await authenticate_ws_actor(websocket, token=token, x_organization_id=org_id)
    except HTTPException as e:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=str(e.detail)[:120])
        return
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
        return

    # Derive organization scope strictly from authenticated identity
    authenticated_org_str = str(actor.organization_id)

    # Disallow attempting to subscribe to a different organization
    if org_id and org_id != authenticated_org_str:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason=f"Forbidden: cannot subscribe to foreign organization events",
        )
        return

    await websocket.accept()
    queue: asyncio.Queue = asyncio.Queue()
    delivered_event_ids: Set[str] = set()

    def _on_event(event_record: Dict[str, Any]):
        try:
            # Strictly filter by authenticated organization identity
            if event_record.get("organization_id") != authenticated_org_str:
                return
            ev_id = event_record.get("event_id")
            if ev_id and ev_id in delivered_event_ids:
                return
            if ev_id:
                delivered_event_ids.add(ev_id)
                if len(delivered_event_ids) > 1000:
                    # Keep set bounded
                    delivered_event_ids.clear()
            queue.put_nowait(event_record)
        except Exception:
            pass

    EventDispatcher.subscribe(_on_event)

    async def _redis_listener():
        try:
            redis_client = get_redis()
            pubsub = redis_client.pubsub()
            # Subscribe ONLY to authenticated organization channel
            channel = f"events:{authenticated_org_str}"
            await pubsub.subscribe(channel)
            async for message in pubsub.listen():
                if message.get("type") in ("pmessage", "message"):
                    try:
                        raw_data = message.get("data")
                        if isinstance(raw_data, bytes):
                            raw_data = raw_data.decode("utf-8")
                        data = json.loads(raw_data)
                        if data.get("organization_id") == authenticated_org_str:
                            ev_id = data.get("event_id")
                            if ev_id and ev_id in delivered_event_ids:
                                continue
                            if ev_id:
                                delivered_event_ids.add(ev_id)
                            queue.put_nowait(data)
                    except Exception:
                        pass
        except Exception:
            pass

    redis_task = asyncio.create_task(_redis_listener())

    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event)
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        EventDispatcher.unsubscribe(_on_event)
        redis_task.cancel()


@router.get(
    "/events/recent",
    summary="Get recent prospecting and agent telemetry events",
)
async def get_recent_events(
    event_type: Optional[str] = Query(None),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> List[Dict[str, Any]]:
    """Retrieve recent telemetry events scoped strictly to authenticated organization."""
    events = EventDispatcher.get_recent_events(event_type=event_type)
    return [e for e in events if e.get("organization_id") == str(org_id)]


@router.get(
    "/dashboard-feed",
    summary="Get aggregated live and historical prospecting feed for dashboard",
)
async def get_dashboard_feed(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> Dict[str, Any]:
    """
    Hydrate the dashboard with durable database candidates, CRM leads, and job execution metrics.
    Ensures persistent visibility across page reloads and browser sessions.
    """
    # 1. Fetch recent candidates for this org
    query = (
        select(ProspectCandidate)
        .where(ProspectCandidate.organization_id == org_id)
        .order_by(ProspectCandidate.first_seen.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    candidates = result.scalars().all()

    # 2. Map linked lead data where available
    lead_ids = [c.linked_lead_id for c in candidates if c.linked_lead_id]
    leads_map: Dict[uuid.UUID, Lead] = {}
    if lead_ids:
        lead_query = select(Lead).where(Lead.id.in_(lead_ids))
        lead_res = await db.execute(lead_query)
        for l in lead_res.scalars().all():
            leads_map[l.id] = l

    prospects_data: List[Dict[str, Any]] = []
    urgent_count = 0

    for c in candidates:
        lead = leads_map.get(c.linked_lead_id) if c.linked_lead_id else None
        meta = dict(c.metadata_json or {})

        service_match = (
            (lead.recommended_service if lead else None)
            or meta.get("recommended_service")
            or "Custom Software / Web Development"
        )
        overall_score = lead.overall_score if lead else (
            int(meta.get("urgency_score", 0)) if meta.get("urgency_score")
            else int((c.confidence or 0.8) * 100)
        )
        intent_score = lead.intent_score if lead else (
            85 if c.status == "QUALIFIED" else (
                50 if c.status == "REVIEW_REQUIRED" else 20
            )
        )

        urgency = meta.get("urgency") or ("HIGH" if c.status == "QUALIFIED" else "MEDIUM")
        if urgency in ("HIGH", "CRITICAL"):
            urgent_count += 1

        urgency_reason = meta.get("urgency_reason") or (
            "Active commercial service requirement detected" if c.status == "QUALIFIED" else None
        )

        country = meta.get("country") or c.location
        country_evidence = meta.get("country_evidence")
        published_at = meta.get("timestamp") or (
            c.first_seen.isoformat() if hasattr(c, "first_seen") and c.first_seen else None
        )

        # Do not expose public webmail or placeholder domains as company websites
        clean_website = c.domain if (c.domain and not is_disallowed_business_domain(c.domain)) else None

        prospects_data.append({
            "candidate_id": str(c.id),
            "lead_id": str(c.linked_lead_id) if c.linked_lead_id else None,
            "platform": c.platform or "THREADS",
            "author": c.username_or_handle or c.company_name or "Unknown Prospect",
            "source_url": c.canonical_url or c.source_url or "#",
            "evidence": c.discovery_evidence or "High intent commercial request identified",
            "website": clean_website,
            "service_match": service_match,
            "urgency": urgency,
            "urgency_reason": urgency_reason,
            "score": overall_score,
            "intent_score": intent_score,
            "status": c.status,
            "country": country,
            "country_evidence": country_evidence,
            "published_at": published_at,
            "created_at": c.first_seen.isoformat() if hasattr(c, "first_seen") and c.first_seen else None,
        })

    # 3. Calculate aggregated metrics across jobs and candidates
    jobs_query = select(ProspectingJob).where(ProspectingJob.organization_id == org_id)
    jobs_res = await db.execute(jobs_query)
    jobs = jobs_res.scalars().all()

    total_pages = sum((j.statistics or {}).get("pages_visited", 0) for j in jobs)
    total_scrolls = sum((j.statistics or {}).get("scrolls_performed", 0) for j in jobs)
    total_candidates = len(candidates)
    # Only genuine QUALIFIED records count toward qualified metric; duplicates and review-required do not
    total_qualified = sum(1 for c in candidates if c.status == "QUALIFIED")
    total_leads = sum(1 for c in candidates if c.status == "CONVERTED_TO_LEAD" or c.linked_lead_id)
    total_drafts = sum((j.statistics or {}).get("outreach_drafted", 0) for j in jobs)

    return {
        "metrics": {
            "pages": total_pages,
            "scrolls": total_scrolls,
            "candidates": total_candidates,
            "qualified": total_qualified,
            "urgent": urgent_count,
            "leads": total_leads,
            "drafts": total_drafts,
        },
        "prospects": prospects_data,
    }


