import uuid
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.agents.conversation.conversation_memory import (
    ConversationContext,
    MessageSummaryItem,
)
from services.api.app.models.conversation import ConversationThread
from services.api.app.repositories.conversation import ConversationRepository
from services.api.app.repositories.crm import (
    CompanyRepository,
    ContactRepository,
    LeadRepository,
    LeadSignalRepository,
)
from services.api.app.repositories.outreach import OutreachRepository
from services.api.app.repositories.research import WebsiteResearchRepository


class ConversationMemoryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.conv_repo = ConversationRepository(session)
        self.lead_repo = LeadRepository(session)
        self.company_repo = CompanyRepository(session)
        self.contact_repo = ContactRepository(session)
        self.signal_repo = LeadSignalRepository(session)
        self.research_repo = WebsiteResearchRepository(session)
        self.outreach_repo = OutreachRepository(session)

    async def build_context(
        self,
        organization_id: uuid.UUID,
        thread: ConversationThread,
    ) -> ConversationContext:
        lead = await self.lead_repo.get_by_id(organization_id, thread.lead_id)

        company_name: Optional[str] = None
        contact_handle: Optional[str] = None

        if lead:
            if lead.company_id:
                comp = await self.company_repo.get_by_id(organization_id, lead.company_id)
                if comp:
                    company_name = comp.name
            if lead.contact_id:
                cnt = await self.contact_repo.get_by_id(organization_id, lead.contact_id)
                if cnt:
                    contact_handle = (
                        cnt.instagram_username
                        or cnt.reddit_username
                        or cnt.email
                        or cnt.full_name
                    )

        # Signals
        signals = await self.signal_repo.list_by_lead(thread.lead_id)
        signals_summary = [f"{s.signal_type}: {s.evidence}" for s in signals[:3]]

        # Website Research
        research = await self.research_repo.get_latest_for_lead(thread.lead_id, organization_id)
        website_findings: List[str] = []
        if research:
            if research.recommendations:
                website_findings.extend(research.recommendations[:2])
            elif research.technology_stack:
                tech_names = [
                    t if isinstance(t, str) else (t.get("technology") or t.get("name"))
                    for t in research.technology_stack
                    if (isinstance(t, str) and t) or (isinstance(t, dict) and (t.get("technology") or t.get("name")))
                ]
                if tech_names:
                    tech_str = ", ".join(tech_names[:3])
                    website_findings.append(f"Detected technologies: {tech_str}")

        # Past outreach body
        past_drafts = await self.outreach_repo.list_drafts_by_lead(organization_id, thread.lead_id)
        previous_outreach_body: Optional[str] = None
        previous_outreach_channel: Optional[str] = None
        if past_drafts:
            latest_draft = past_drafts[0]
            previous_outreach_body = latest_draft.body
            previous_outreach_channel = latest_draft.channel

        # Recent messages in thread
        messages = await self.conv_repo.list_messages_by_thread(organization_id, thread.id)
        recent_items = [
            MessageSummaryItem(
                direction=m.direction,
                author_type=m.author_type,
                content=m.content,
                created_at=m.created_at.isoformat() if m.created_at else None,
            )
            for m in messages[-10:]
        ]

        return ConversationContext(
            lead_id=str(thread.lead_id),
            organization_id=str(organization_id),
            lead_title=lead.title if lead else None,
            company_name=company_name,
            contact_handle=contact_handle,
            recommended_service=lead.recommended_service if lead else None,
            lead_score=lead.overall_score if lead else 0,
            signals_summary=signals_summary,
            website_findings=website_findings,
            previous_outreach_body=previous_outreach_body,
            previous_outreach_channel=previous_outreach_channel,
            recent_messages=recent_items,
            current_summary=thread.summary,
            sales_stage=thread.sales_stage,
            latest_intent=thread.current_intent,
        )
