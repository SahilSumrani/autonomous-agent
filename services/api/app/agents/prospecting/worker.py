import asyncio
import logging
import uuid
from typing import Dict, Optional

from packages.shared_types.prospecting import ProspectingJobStatus
from services.api.app.agents.prospecting.orchestrator import ProspectingOrchestrator
from services.api.app.core.database import AsyncSessionLocal
from services.api.app.repositories.prospecting import ProspectingJobRepository

logger = logging.getLogger("techverse.agent.prospecting.worker")


class ProspectingWorker:
    """
    Background worker executing prospecting jobs asynchronously outside the HTTP request loop.
    Enforces task tracking, exception safety, and restart resilience.
    """

    def __init__(self):
        self._running_tasks: Dict[uuid.UUID, asyncio.Task] = {}
        self._pause_requested: set[uuid.UUID] = set()
        self._cancel_requested: set[uuid.UUID] = set()

    def is_job_running(self, job_id: uuid.UUID) -> bool:
        task = self._running_tasks.get(job_id)
        return bool(task and not task.done())

    def request_pause(self, job_id: uuid.UUID) -> None:
        """Signal cooperative pause to the running job loop."""
        self._pause_requested.add(job_id)

    def request_cancel(self, job_id: uuid.UUID) -> None:
        """Signal cooperative cancellation to the running job loop."""
        self._cancel_requested.add(job_id)

    def is_pause_requested(self, job_id: uuid.UUID) -> bool:
        return job_id in self._pause_requested

    def is_cancel_requested(self, job_id: uuid.UUID) -> bool:
        return job_id in self._cancel_requested

    def clear_flags(self, job_id: uuid.UUID) -> None:
        self._pause_requested.discard(job_id)
        self._cancel_requested.discard(job_id)

    def start_job_task(
        self,
        job_id: uuid.UUID,
        organization_id: uuid.UUID,
        session_id: Optional[uuid.UUID] = None,
    ) -> asyncio.Task:
        """Spawn background task for autonomous job execution."""
        self.clear_flags(job_id)
        if self.is_job_running(job_id):
            logger.info(f"Job {job_id} is already actively running in background.")
            return self._running_tasks[job_id]

        task = asyncio.create_task(
            self._execute_job_in_background(job_id, organization_id, session_id),
            name=f"prospecting_job_{job_id}",
        )
        self._running_tasks[job_id] = task

        def _cleanup_callback(t: asyncio.Task):
            self._running_tasks.pop(job_id, None)
            self.clear_flags(job_id)
            if not t.cancelled() and t.exception():
                logger.error(f"Background task for job {job_id} encountered unhandled exception: {t.exception()}")

        task.add_done_callback(_cleanup_callback)
        return task

    def cancel_job_task(self, job_id: uuid.UUID) -> bool:
        """Cancel an in-flight background task safely."""
        self.request_cancel(job_id)
        task = self._running_tasks.get(job_id)
        if task and not task.done():
            task.cancel()
            self._running_tasks.pop(job_id, None)
            return True
        return False

    async def _execute_job_in_background(
        self,
        job_id: uuid.UUID,
        organization_id: uuid.UUID,
        session_id: Optional[uuid.UUID] = None,
    ) -> None:
        logger.info(f"Starting background prospecting execution for job {job_id}")
        async with AsyncSessionLocal() as db_session:
            try:
                orchestrator = ProspectingOrchestrator(db_session)
                await orchestrator.execute_job(
                    job_id=job_id,
                    organization_id=organization_id,
                    override_session_id=session_id,
                )
            except asyncio.CancelledError:
                logger.info(f"Background task for job {job_id} was cancelled.")
                try:
                    repo = ProspectingJobRepository(db_session)
                    await repo.update_status(
                        job_id,
                        organization_id,
                        ProspectingJobStatus.CANCELLED,
                        failure_reason="Job cancelled by operator",
                    )
                    await db_session.commit()
                except Exception as e:
                    logger.warning(f"Error updating cancelled job state: {e}")
            except Exception as e:
                logger.error(f"Fatal error in background prospecting job {job_id}: {e}", exc_info=True)
                try:
                    repo = ProspectingJobRepository(db_session)
                    await repo.update_status(
                        job_id,
                        organization_id,
                        ProspectingJobStatus.FAILED,
                        failure_reason=str(e),
                    )
                    await db_session.commit()
                except Exception as inner_e:
                    logger.error(f"Failed to record failure status for job {job_id}: {inner_e}")


# Singleton worker instance
prospecting_worker = ProspectingWorker()
