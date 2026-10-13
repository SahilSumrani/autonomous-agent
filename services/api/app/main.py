from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
import os
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from packages.config.settings import settings
from services.api.app.api.v1.router import api_v1_router
from services.api.app.api.v1.routes.health import get_health_status
from services.api.app.core.database import check_database_health
from services.api.app.core.logging import get_logger, setup_logging
from services.api.app.core.redis import check_redis_health, close_redis
from services.api.app.middleware.request_context import RequestContextMiddleware

# Initialize Structured Logging
setup_logging()
logger = get_logger("main")



@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and shutdown routines."""
    logger.info(
        "Application Starting Up",
        app_name=settings.APP_NAME,
        env=settings.ENVIRONMENT,
        ai_provider=settings.AI_PROVIDER,
    )

    # Preflight connectivity check (non-blocking for local dev)
    db_status = await check_database_health()
    redis_status = await check_redis_health()
    logger.info(
        "Preflight Infrastructure Connectivity",
        database_ready=db_status,
        redis_ready=redis_status,
    )

    # Bootstrap deterministic development organization if in development/test
    if db_status and settings.ENVIRONMENT in ("development", "test"):
        try:
            from database.seeds.dev_seed import seed_development_organization
            dev_org = await seed_development_organization()
            logger.info(
                "Development Organization Bootstrapped",
                org_id=str(dev_org.id),
                org_slug=dev_org.slug,
            )
        except Exception as e:
            logger.warning("Failed to bootstrap development organization", error=str(e))

    yield

    logger.info("Application Shutting Down")
    await close_redis()


app = FastAPI(
    title=settings.APP_NAME,
    version="2.0.0",
    description="TechVerse AI Client Acquisition Operating System — Core Backend API",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# CORS Policy
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Context & Observability Middleware
app.add_middleware(RequestContextMiddleware)

# Root Health Route for Container / Load Balancer Probes
app.add_api_route(
    "/health",
    get_health_status,
    methods=["GET"],
    tags=["Root Health"],
    include_in_schema=True,
)

# Mount API v1 Routers
app.include_router(api_v1_router, prefix=settings.API_V1_STR)


@app.get("/dashboard", response_class=HTMLResponse, tags=["Dashboard"])
async def get_dashboard():
    """Serve real-time autonomous prospecting and client discovery dashboard."""
    dashboard_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "apps", "web", "index.html")
    )
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path)
    return HTMLResponse("<h1>Dashboard not found</h1>", status_code=404)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all unhandled exception handler with structured error logging."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(
        "Unhandled Server Exception",
        request_id=request_id,
        path=request.url.path,
        error=str(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred. Please contact support with the request ID.",
            "request_id": request_id,
        },
    )
