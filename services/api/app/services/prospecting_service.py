import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared_types.prospecting import (
    CandidateStatus,
    ProspectingJobEndReason,
    ProspectingJobStatus,
    ProspectingSourceType,
)
from services.api.app.models.prospecting import (
    ProspectCandidate,
    ProspectObservation,
    ProspectingJob,
)
from services.api.app.repositories.prospecting import (
    ProspectCandidateRepository,
    ProspectObservationRepository,
    ProspectingJobRepository,
)
from services.api.app.schemas.prospecting import ProspectingJobCreate
from services.api.app.services.event_dispatcher import EventDispatcher


class ProspectingServiceException(Exception):
    """Base exception for prospecting service operations."""
    pass


class JobNotFoundException(ProspectingServiceException):
    """Raised when a prospecting job is not found."""
    pass


class ProspectingService:
    """Service managing first-class prospecting jobs and candidates."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.job_repo = ProspectingJobRepository(session)
        self.candidate_repo = ProspectCandidateRepository(session)
        self.observation_repo = ProspectObservationRepository(session)

    async def create_job(
        self,
        organization_id: uuid.UUID,
        data: ProspectingJobCreate,
    ) -> ProspectingJob:
        job = ProspectingJob(
            organization_id=organization_id,
            session_id=data.session_id,
            status=ProspectingJobStatus.CREATED.value,
            source=data.source.value,
            query=data.query,
            target_service=data.target_service,
            target_industries=data.target_industries,
            target_geography=data.target_geography,
            max_candidates=data.max_candidates,
            max_pages=data.max_pages,
            max_scrolls=data.max_scrolls,
            max_time_seconds=data.max_time_seconds,
            metadata_json=data.metadata,
        )
        created = await self.job_repo.create(job)
        await self.session.commit()
        await self.session.refresh(created)

        await EventDispatcher.dispatch(
            event_type="prospecting.job.created",
            data={
                "job_id": str(created.id),
                "source": created.source,
                "query": created.query,
            },
            organization_id=organization_id,
        )
        return created

    async def get_job(
        self,
        organization_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> ProspectingJob:
        job = await self.job_repo.get_by_id(job_id, organization_id)
        if not job:
            raise JobNotFoundException(f"Prospecting job {job_id} not found")
        return job

    async def list_jobs(
        self,
        organization_id: uuid.UUID,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[ProspectingJob], int]:
        return await self.job_repo.list_by_org(
            org_id=organization_id,
            status=status,
            limit=limit,
            offset=offset,
        )

    async def pause_job(
        self,
        organization_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> ProspectingJob:
        job = await self.get_job(organization_id, job_id)
        if job.status not in (ProspectingJobStatus.RUNNING.value, ProspectingJobStatus.QUEUED.value):
            return job
        updated = await self.job_repo.update_status(
            job_id=job_id,
            org_id=organization_id,
            status=ProspectingJobStatus.PAUSED,
        )
        await self.session.commit()
        await self.session.refresh(updated)
        await EventDispatcher.dispatch(
            event_type="prospecting.job.paused",
            data={"job_id": str(job_id)},
            organization_id=organization_id,
        )
        return updated

    async def resume_job(
        self,
        organization_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> ProspectingJob:
        job = await self.get_job(organization_id, job_id)
        if job.status not in (ProspectingJobStatus.PAUSED.value, ProspectingJobStatus.WAITING_FOR_USER.value):
            return job
        updated = await self.job_repo.update_status(
            job_id=job_id,
            org_id=organization_id,
            status=ProspectingJobStatus.QUEUED,
        )
        await self.session.commit()
        await self.session.refresh(updated)
        await EventDispatcher.dispatch(
            event_type="prospecting.job.resumed",
            data={"job_id": str(job_id)},
            organization_id=organization_id,
        )
        return updated

    async def cancel_job(
        self,
        organization_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> ProspectingJob:
        job = await self.get_job(organization_id, job_id)
        updated = await self.job_repo.update_status(
            job_id=job_id,
            org_id=organization_id,
            status=ProspectingJobStatus.CANCELLED,
            failure_reason="Cancelled by user request",
            end_reason=ProspectingJobEndReason.CANCELLED,
        )
        await self.session.commit()
        await self.session.refresh(updated)
        await EventDispatcher.dispatch(
            event_type="prospecting.job.cancelled",
            data={"job_id": str(job_id)},
            organization_id=organization_id,
        )
        return updated

    async def list_candidates(
        self,
        organization_id: uuid.UUID,
        job_id: uuid.UUID,
        status: Optional[str] = None,
    ) -> List[ProspectCandidate]:
        # Validate job existence
        await self.get_job(organization_id, job_id)
        return await self.candidate_repo.list_by_job(
            job_id=job_id,
            org_id=organization_id,
            status=status,
        )

    async def list_observations(
        self,
        organization_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> List[ProspectObservation]:
        await self.get_job(organization_id, job_id)
        return await self.observation_repo.list_by_job(
            job_id=job_id,
            org_id=organization_id,
        )
