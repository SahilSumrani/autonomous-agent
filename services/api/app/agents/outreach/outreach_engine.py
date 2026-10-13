from typing import Any, Dict, List, Optional
from services.api.app.models.crm import Company, Contact, Lead, LeadSignal, LeadSource
from packages.shared_types.outreach import OutreachChannel
from services.api.app.agents.outreach.context_builder import OutreachContextBuilder
from services.api.app.agents.outreach.message_generator import MessageGenerator
from services.api.app.agents.outreach.outreach_models import (
    OutreachContext,
    OutreachDraftResult,
)
from services.api.app.models.research import WebsiteResearch


class OutreachEngine:
    """Core outreach pipeline converting qualified researched leads into validated outreach drafts."""

    @classmethod
    def execute(
        cls,
        lead: Lead,
        company: Optional[Company] = None,
        contact: Optional[Contact] = None,
        sources: Optional[List[LeadSource]] = None,
        signals: Optional[List[LeadSignal]] = None,
        website_research: Optional[WebsiteResearch] = None,
        channel: Optional[OutreachChannel] = None,
        variant_count: int = 3,
        preferences: Optional[List[str]] = None,
    ) -> (OutreachContext, List[OutreachDraftResult]):
        # 1. Build unified evidence context
        context = OutreachContextBuilder.build_context(
            lead=lead,
            company=company,
            contact=contact,
            sources=sources,
            signals=signals,
            website_research=website_research,
        )

        target_channel = channel or context.recommended_channel

        # 2. Generate and validate variants
        drafts = MessageGenerator.generate_variants(
            context=context,
            channel=target_channel,
            variant_count=variant_count,
            preferences=preferences,
        )

        return context, drafts

    @classmethod
    async def execute_async(
        cls,
        lead: Lead,
        company: Optional[Company] = None,
        contact: Optional[Contact] = None,
        sources: Optional[List[LeadSource]] = None,
        signals: Optional[List[LeadSignal]] = None,
        website_research: Optional[WebsiteResearch] = None,
        channel: Optional[OutreachChannel] = None,
        variant_count: int = 3,
        preferences: Optional[List[str]] = None,
        ai_provider: Optional[Any] = None,
    ) -> (OutreachContext, List[OutreachDraftResult]):
        # 1. Build unified evidence context
        context = OutreachContextBuilder.build_context(
            lead=lead,
            company=company,
            contact=contact,
            sources=sources,
            signals=signals,
            website_research=website_research,
        )

        target_channel = channel or context.recommended_channel

        # 2. Generate and validate variants (with AI provider if configured)
        drafts = await MessageGenerator.generate_variants_async(
            context=context,
            channel=target_channel,
            variant_count=variant_count,
            preferences=preferences,
            ai_provider=ai_provider,
        )

        return context, drafts
