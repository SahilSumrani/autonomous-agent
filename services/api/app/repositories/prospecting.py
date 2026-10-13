import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import desc, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from packages.shared_types.prospecting import (
    CandidateStatus,
    ProspectingJobStatus,
)
from services.api.app.models.prospecting import (
    ProspectCandidate,
    ProspectObservation,
    ProspectingJob,
    ProspectingProfile,
)


class ProspectingJobRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, job: ProspectingJob) -> ProspectingJob:
        self.session.add(job)
        await self.session.flush()
        await self.session.refresh(job)
        return job

    async def get_by_id(self, job_id: uuid.UUID, org_id: uuid.UUID) -> Optional[ProspectingJob]:
        query = (
            select(ProspectingJob)
            .where(
                ProspectingJob.id == job_id,
                ProspectingJob.organization_id == org_id,
            )
            .options(
                selectinload(ProspectingJob.candidates),
                selectinload(ProspectingJob.observations),
            )
        )
        res = await self.session.execute(query)
        return res.scalar_one_or_none()

    async def list_by_org(
        self,
        org_id: uuid.UUID,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[ProspectingJob], int]:
        query = select(ProspectingJob).where(ProspectingJob.organization_id == org_id)
        count_query = select(func.count(ProspectingJob.id)).where(ProspectingJob.organization_id == org_id)
        
        if status:
            query = query.where(ProspectingJob.status == status)
            count_query = count_query.where(ProspectingJob.status == status)

        query = query.order_by(desc(ProspectingJob.created_at)).limit(limit).offset(offset)

        total_res = await self.session.execute(count_query)
        total = total_res.scalar() or 0

        items_res = await self.session.execute(query)
        items = list(items_res.scalars().all())

        return items, total

    async def update_status(
        self,
        job_id: uuid.UUID,
        org_id: uuid.UUID,
        status: ProspectingJobStatus,
        failure_reason: Optional[str] = None,
        end_reason: Optional[Any] = None,
    ) -> Optional[ProspectingJob]:
        job = await self.get_by_id(job_id, org_id)
        if not job:
            return None
        status_val = status.value if hasattr(status, "value") else str(status)
        job.status = status_val
        if failure_reason:
            job.failure_reason = failure_reason
        if end_reason is not None:
            job.end_reason = end_reason.value if hasattr(end_reason, "value") else str(end_reason)
        if status_val == ProspectingJobStatus.RUNNING.value and not job.started_at:
            job.started_at = datetime.now(timezone.utc)
        elif status_val in (
            ProspectingJobStatus.COMPLETED.value,
            ProspectingJobStatus.FAILED.value,
            ProspectingJobStatus.CANCELLED.value,
            ProspectingJobStatus.BLOCKED.value,
        ):
            job.completed_at = datetime.now(timezone.utc)
        await self.session.flush()
        return job

    async def update_statistics(
        self,
        job_id: uuid.UUID,
        org_id: uuid.UUID,
        statistics: Dict[str, Any],
    ) -> Optional[ProspectingJob]:
        job = await self.get_by_id(job_id, org_id)
        if not job:
            return None
        merged = dict(job.statistics)
        merged.update(statistics)
        job.statistics = merged
        await self.session.flush()
        return job


class ProspectCandidateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, candidate: ProspectCandidate) -> ProspectCandidate:
        self.session.add(candidate)
        await self.session.flush()
        await self.session.refresh(candidate)
        return candidate

    async def get_by_id(self, candidate_id: uuid.UUID, org_id: uuid.UUID) -> Optional[ProspectCandidate]:
        query = (
            select(ProspectCandidate)
            .where(
                ProspectCandidate.id == candidate_id,
                ProspectCandidate.organization_id == org_id,
            )
            .options(selectinload(ProspectCandidate.observations))
        )
        res = await self.session.execute(query)
        return res.scalar_one_or_none()

    async def get_by_dedup_key(
        self,
        job_id: uuid.UUID,
        dedup_key: str,
    ) -> Optional[ProspectCandidate]:
        query = select(ProspectCandidate).where(
            ProspectCandidate.job_id == job_id,
            ProspectCandidate.dedup_key == dedup_key,
        )
        res = await self.session.execute(query)
        return res.scalar_one_or_none()

    async def find_global_duplicate(
        self,
        org_id: uuid.UUID,
        dedup_key: str,
    ) -> Optional[ProspectCandidate]:
        query = (
            select(ProspectCandidate)
            .where(
                ProspectCandidate.organization_id == org_id,
                ProspectCandidate.dedup_key == dedup_key,
            )
            .order_by(desc(ProspectCandidate.last_seen))
            .limit(1)
        )
        res = await self.session.execute(query)
        return res.scalar_one_or_none()

    async def list_by_job(
        self,
        job_id: uuid.UUID,
        org_id: uuid.UUID,
        status: Optional[str] = None,
    ) -> List[ProspectCandidate]:
        query = select(ProspectCandidate).where(
            ProspectCandidate.job_id == job_id,
            ProspectCandidate.organization_id == org_id,
        )
        if status:
            query = query.where(ProspectCandidate.status == status)
        query = query.order_by(desc(ProspectCandidate.confidence), desc(ProspectCandidate.last_seen))
        res = await self.session.execute(query)
        return list(res.scalars().all())

    async def update_status(
        self,
        candidate_id: uuid.UUID,
        org_id: uuid.UUID,
        status: CandidateStatus,
        confidence: Optional[float] = None,
        linked_lead_id: Optional[uuid.UUID] = None,
    ) -> Optional[ProspectCandidate]:
        cand = await self.get_by_id(candidate_id, org_id)
        if not cand:
            return None
        cand.status = status.value
        cand.last_seen = datetime.now(timezone.utc)
        if confidence is not None:
            cand.confidence = confidence
        if linked_lead_id is not None:
            cand.linked_lead_id = linked_lead_id
        await self.session.flush()
        return cand


class ProspectObservationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, observation: ProspectObservation) -> ProspectObservation:
        self.session.add(observation)
        await self.session.flush()
        await self.session.refresh(observation)
        return observation

    async def list_by_candidate(
        self,
        candidate_id: uuid.UUID,
        org_id: uuid.UUID,
    ) -> List[ProspectObservation]:
        query = (
            select(ProspectObservation)
            .where(
                ProspectObservation.candidate_id == candidate_id,
                ProspectObservation.organization_id == org_id,
            )
            .order_by(desc(ProspectObservation.created_at))
        )
        res = await self.session.execute(query)
        return list(res.scalars().all())

    async def list_by_job(
        self,
        job_id: uuid.UUID,
        org_id: uuid.UUID,
    ) -> List[ProspectObservation]:
        query = (
            select(ProspectObservation)
            .where(
                ProspectObservation.job_id == job_id,
                ProspectObservation.organization_id == org_id,
            )
            .order_by(desc(ProspectObservation.created_at))
        )
        res = await self.session.execute(query)
        return list(res.scalars().all())

    async def get_by_hash(
        self,
        job_id: uuid.UUID,
        content_hash: str,
    ) -> Optional[ProspectObservation]:
        query = select(ProspectObservation).where(
            ProspectObservation.job_id == job_id,
            ProspectObservation.content_hash == content_hash,
        ).limit(1)
        res = await self.session.execute(query)
        return res.scalar_one_or_none()


class ProspectingProfileRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, org_id: uuid.UUID) -> ProspectingProfile:
        query = select(ProspectingProfile).where(ProspectingProfile.organization_id == org_id)
        res = await self.session.execute(query)
        profile = res.scalar_one_or_none()
        if not profile:
            profile = ProspectingProfile(
                organization_id=org_id,
                services_offered=["AI automation", "Web Development", "Mobile Apps", "Custom Software"],
                ideal_customer_keywords=[
                    "need a website",
                    "looking for developer",
                    "build MVP",
                    "automation workflow",
                    "website redesign",
                    "hire developer",
                ],
                excluded_keywords=[
                    "student",
                    "homework",
                    "free",
                    "internship",
                    "hiring employee",
                    "full-time job",
                ],
                sources_enabled=["REDDIT", "THREADS", "WEBSITE"],
                daily_limits_json={"REDDIT": 25, "THREADS": 25, "WEBSITE": 50, "LINKEDIN": 10},
                geography="Global",
            )
            self.session.add(profile)
            await self.session.flush()
            await self.session.refresh(profile)
        return profile

    async def update(
        self,
        org_id: uuid.UUID,
        update_data: Dict[str, Any],
    ) -> ProspectingProfile:
        profile = await self.get_or_create(org_id)
        for key, value in update_data.items():
            if value is not None and hasattr(profile, key):
                setattr(profile, key, value)
        await self.session.flush()
        await self.session.refresh(profile)
        return profile

