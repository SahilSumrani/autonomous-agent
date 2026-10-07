from fastapi import APIRouter
from services.api.app.api.v1.routes import health

api_v1_router = APIRouter()

# Health & Readiness
api_v1_router.include_router(health.router)
