from datetime import datetime, timezone
from fastapi import APIRouter, status
from pydantic import BaseModel
from packages.config.settings import settings
from services.api.app.core.database import check_database_health
from services.api.app.core.redis import check_redis_health

router = APIRouter(tags=["Health"])


class ComponentHealth(BaseModel):
    status: str
    details: str | None = None


class HealthResponse(BaseModel):
    status: str
    environment: str
    timestamp: str
    ai_provider: str
    database: ComponentHealth
    redis: ComponentHealth


@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def get_health_status() -> HealthResponse:
    """Return health status of API, database, and Redis cache."""
    db_ok = await check_database_health()
    redis_ok = await check_redis_health()

    overall_status = "healthy" if (db_ok and redis_ok) else "degraded"

    return HealthResponse(
        status=overall_status,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc).isoformat(),
        ai_provider=settings.AI_PROVIDER,
        database=ComponentHealth(
            status="connected" if db_ok else "disconnected",
            details="PostgreSQL connection operational" if db_ok else "Could not reach database",
        ),
        redis=ComponentHealth(
            status="connected" if redis_ok else "disconnected",
            details="Redis connection operational" if redis_ok else "Could not reach Redis cache",
        ),
    )
