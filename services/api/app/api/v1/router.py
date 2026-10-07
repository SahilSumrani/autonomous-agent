from fastapi import APIRouter
from services.api.app.api.v1.routes import (
    agent,
    browser_gateway,
    companies,
    contacts,
    health,
    leads,
    outreach,
    research,
    conversations,
)

api_v1_router = APIRouter()

# Health & Readiness
api_v1_router.include_router(health.router)

# CRM Core
api_v1_router.include_router(companies.router)
api_v1_router.include_router(contacts.router)
api_v1_router.include_router(leads.router)

# Browser Research Agent & Gateway
api_v1_router.include_router(agent.router)
api_v1_router.include_router(browser_gateway.router)

# Website Intelligence & Deep Research
api_v1_router.include_router(research.router)

# Outreach Intelligence & Approvals
api_v1_router.include_router(outreach.router)

# Conversation Intelligence & Reply Agent
api_v1_router.include_router(conversations.router)

