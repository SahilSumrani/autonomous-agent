from fastapi import APIRouter
from services.api.app.api.v1.routes import agent, companies, contacts, health, leads

api_v1_router = APIRouter()

# Health & Readiness
api_v1_router.include_router(health.router)

# CRM Core
api_v1_router.include_router(companies.router)
api_v1_router.include_router(contacts.router)
api_v1_router.include_router(leads.router)

# Browser Research Agent
api_v1_router.include_router(agent.router)
