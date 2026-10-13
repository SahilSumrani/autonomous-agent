import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared_types.crm import LeadStatus
from packages.shared_types.outreach import (
    ApprovalDecision,
    DraftStatus,
    OutreachChannel,
)
from services.api.app.agents.outreach.message_validator import MessageValidator
from services.api.app.agents.outreach.outreach_engine import OutreachEngine
from services.api.app.agents.outreach.outreach_models import (
    MessageValidationResult,
    OutreachDraftResult,
)
from services.api.app.models.crm import Lead, LeadSignal, LeadSource
from services.api.app.models.outreach import OutreachDraft
from services.api.app.repositories.crm import (
    CompanyRepository,
    ContactRepository,
    LeadRepository,
    LeadSignalRepository,
    LeadSourceRepository,
)
from services.api.app.repositories.outreach import OutreachRepository
from services.api.app.repositories.research import WebsiteResearchRepository
from services.api.app.providers.ai.factory import get_ai_provider
from services.api.app.services.event_dispatcher import EventDispatcher
from services.api.app.services.outreach_history import OutreachHistoryManager


class DuplicateOutreachBlockedError(ValueError):
    """Raised when duplicate outreach protection blocks a draft generation."""
    pass


class OutreachService:
    """Orchestrates end-to-end outreach context, generation, validation, and human approvals."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.outreach_repo = OutreachRepository(session)
        self.lead_repo = LeadRepository(session)
        self.company_repo = CompanyRepository(session)
        self.contact_repo = ContactRepository(session)
        self.signal_repo = LeadSignalRepository(session)
        self.research_repo = WebsiteResearchRepository(session)
        self.history_mgr = OutreachHistoryManager(session)

    async def generate_outreach(
        self,
        organization_id: uuid.UUID,
        lead_id: uuid.UUID,
        channel: Optional[OutreachChannel] = None,
        variant_count: int = 3,
        preferences: Optional[List[str]] = None,
        override_duplicate: bool = False,
    ) -> List[OutreachDraft]:
        lead = await self.lead_repo.get_by_id(organization_id, lead_id)
        if not lead:
            raise ValueError(f"Lead {lead_id} not found for organization {organization_id}")

        target_channel = channel or OutreachChannel.INSTAGRAM_DM

        # 1. Duplicate outreach protection
        allowed, reason = await self.history_mgr.check_duplicate_protection(
            organization_id=organization_id,
            lead_id=lead_id,
            channel=target_channel,
            recipient=lead.title,
            override_duplicate=override_duplicate,
        )
        if not allowed:
            await self.outreach_repo.record_attempt(
                organization_id=organization_id,
                lead_id=lead_id,
                channel=target_channel.value,
                status="BLOCKED",
                recipient=lead.title,
                reason=reason,
            )
            await EventDispatcher.emit(
                event_type="lead.outreach.blocked",
                org_id=organization_id,
                lead_id=lead_id,
                payload={"channel": target_channel.value, "reason": reason},
            )
            await self.session.commit()
            raise DuplicateOutreachBlockedError(reason)

        # 2. Gather context dependencies
        company = None
        if lead.company_id:
            company = await self.company_repo.get_by_id(organization_id, lead.company_id)

        contact = None
        if lead.contact_id:
            contact = await self.contact_repo.get_by_id(organization_id, lead.contact_id)

        # Enforce verified recipient email requirement for email outreach
        if target_channel == OutreachChannel.EMAIL:
            recipient_email = None
            if contact and getattr(contact, "email", None):
                recipient_email = contact.email
            elif company and getattr(company, "email", None):
                recipient_email = company.email
            elif getattr(lead, "email", None):
                recipient_email = lead.email

            if not recipient_email:
                reason = "No verified recipient email available for email outreach"
                await self.outreach_repo.record_attempt(
                    organization_id=organization_id,
                    lead_id=lead_id,
                    channel=target_channel.value,
                    status="BLOCKED",
                    recipient=lead.title,
                    reason=reason,
                )
                await EventDispatcher.emit(
                    event_type="lead.outreach.blocked",
                    org_id=organization_id,
                    lead_id=lead_id,
                    payload={"channel": target_channel.value, "reason": reason},
                )
                await self.session.commit()
                raise ValueError(reason)

        # Fetch signals
        signals = await self.signal_repo.list_by_lead(lead_id)

        # Fetch website research
        website_research = await self.research_repo.get_by_lead_id(organization_id, lead_id)

        # Sources
        sources: List[LeadSource] = []
        if lead.source_id:
            stmt = select(LeadSource).where(LeadSource.id == lead.source_id, LeadSource.organization_id == organization_id)
            res = await self.session.execute(stmt)
            src = res.scalar_one_or_none()
            if src:
                sources.append(src)

        # 3. Resolve configured AI provider if available (with deterministic fallback)
        ai_provider = None
        try:
            ai_provider = get_ai_provider()
        except Exception:
            ai_provider = None

        # Execute outreach engine
        context, draft_results = await OutreachEngine.execute_async(
            lead=lead,
            company=company,
            contact=contact,
            sources=sources,
            signals=signals,
            website_research=website_research,
            channel=target_channel,
            variant_count=variant_count,
            preferences=preferences,
            ai_provider=ai_provider,
        )

        await EventDispatcher.emit(
            event_type="lead.outreach.context.created",
            org_id=organization_id,
            lead_id=lead_id,
            payload={
                "recommended_channel": context.recommended_channel.value,
                "recommended_angle": context.recommended_angle.value,
                "evidence_count": len(context.evidence),
                "pain_points_count": len(context.pain_points),
            },
        )

        # 4. Supersede previous active drafts for this channel
        await self.outreach_repo.supersede_previous_drafts(
            organization_id=organization_id,
            lead_id=lead_id,
            channel=target_channel.value,
        )

        saved_drafts: List[OutreachDraft] = []
        any_ready_for_approval = False

        for d_res in draft_results:
            draft = await self.outreach_repo.create_draft(
                organization_id=organization_id,
                lead_id=lead_id,
                channel=d_res.channel.value,
                variant=d_res.variant,
                subject=d_res.subject,
                body=d_res.body,
                personalization_level=d_res.personalization_level.value,
                angle=d_res.angle.value,
                recommended_service=d_res.service,
                quality_score=d_res.quality_score,
                confidence=context.confidence,
                status=d_res.status.value,
                cta_text=d_res.cta_text,
                cta_category=d_res.cta_category.value if d_res.cta_category else None,
                metadata_json={
                    "preferences": preferences or [],
                    "validation": d_res.validation_result.model_dump() if d_res.validation_result else None,
                },
            )

            # Save evidences
            for ev in d_res.evidence_items:
                await self.outreach_repo.add_evidence(
                    organization_id=organization_id,
                    draft_id=draft.id,
                    claim=ev.claim,
                    evidence_text=ev.evidence_text,
                    evidence_type=ev.evidence_type,
                    source_url=ev.source_url,
                    confidence=ev.confidence,
                )

            # Create approval gate if draft is ready
            if d_res.status == DraftStatus.READY_FOR_APPROVAL:
                any_ready_for_approval = True
                await self.outreach_repo.create_approval(
                    organization_id=organization_id,
                    lead_id=lead_id,
                    draft_id=draft.id,
                    channel=draft.channel,
                    requested_by="SYSTEM",
                )
                await EventDispatcher.emit(
                    event_type="lead.outreach.ready_for_approval",
                    org_id=organization_id,
                    lead_id=lead_id,
                    payload={"draft_id": str(draft.id), "variant": draft.variant, "score": draft.quality_score},
                )

            await EventDispatcher.emit(
                event_type="lead.outreach.generated",
                org_id=organization_id,
                lead_id=lead_id,
                payload={"draft_id": str(draft.id), "variant": draft.variant, "channel": draft.channel},
            )

            saved_drafts.append(draft)

        # 5. Update CRM lead status to OUTREACH_READY if approved-ready draft exists
        if any_ready_for_approval and lead.status not in [LeadStatus.APPROVED.value, LeadStatus.CONTACTED.value]:
            lead.status = LeadStatus.OUTREACH_READY.value
            lead.updated_at = datetime.now(timezone.utc)

        # Record attempt
        await self.outreach_repo.record_attempt(
            organization_id=organization_id,
            lead_id=lead_id,
            channel=target_channel.value,
            status="GENERATED",
            recipient=lead.title,
            reason="Generated outreach variants.",
        )

        await self.session.commit()

        # Re-fetch drafts with loaded evidences and approvals
        return await self.outreach_repo.list_drafts_by_lead(organization_id, lead_id)

    async def get_draft(
        self,
        organization_id: uuid.UUID,
        draft_id: uuid.UUID,
    ) -> Optional[OutreachDraft]:
        return await self.outreach_repo.get_draft_by_id(organization_id, draft_id)

    async def list_drafts(
        self,
        organization_id: uuid.UUID,
        lead_id: uuid.UUID,
    ) -> List[OutreachDraft]:
        return await self.outreach_repo.list_drafts_by_lead(organization_id, lead_id)

    async def validate_draft(
        self,
        organization_id: uuid.UUID,
        draft_id: uuid.UUID,
    ) -> Tuple[Optional[OutreachDraft], Optional[MessageValidationResult]]:
        draft = await self.outreach_repo.get_draft_by_id(organization_id, draft_id)
        if not draft:
            return None, None

        lead = await self.lead_repo.get_by_id(organization_id, draft.lead_id)
        if not lead:
            return None, None

        company = await self.company_repo.get_by_id(organization_id, lead.company_id) if lead.company_id else None
        contact = await self.contact_repo.get_by_id(organization_id, lead.contact_id) if lead.contact_id else None
        signals = await self.signal_repo.list_by_lead(lead.id)
        website_research = await self.research_repo.get_by_lead_id(organization_id, lead.id)

        context, _ = OutreachEngine.execute(
            lead=lead,
            company=company,
            contact=contact,
            signals=signals,
            website_research=website_research,
            channel=OutreachChannel(draft.channel),
            variant_count=1,
        )

        val_res = MessageValidator.validate_draft(
            body=draft.body,
            context=context,
            channel=OutreachChannel(draft.channel),
        )

        new_status = DraftStatus.READY_FOR_APPROVAL.value if val_res.valid else DraftStatus.NEEDS_REVIEW.value
        updated_draft = await self.outreach_repo.update_draft_status(
            organization_id=organization_id,
            draft_id=draft_id,
            status=new_status,
            quality_score=val_res.score,
        )

        await EventDispatcher.emit(
            event_type="lead.outreach.validated",
            org_id=organization_id,
            lead_id=draft.lead_id,
            payload={"draft_id": str(draft_id), "valid": val_res.valid, "score": val_res.score},
        )
        await self.session.commit()
        return updated_draft, val_res

    async def approve_draft(
        self,
        organization_id: uuid.UUID,
        draft_id: uuid.UUID,
        reviewed_by: Optional[str] = "SAHIL",
        decision_reason: Optional[str] = "Approved outreach draft.",
    ) -> Optional[OutreachDraft]:
        draft = await self.outreach_repo.get_draft_by_id(organization_id, draft_id)
        if not draft:
            return None

        # 1. Enforce state machine transition: must be READY_FOR_APPROVAL
        if draft.status not in (DraftStatus.READY_FOR_APPROVAL.value, DraftStatus.APPROVED.value):
            raise ValueError(
                f"Illegal state transition: cannot approve draft in state '{draft.status}'. Only READY_FOR_APPROVAL drafts can be approved."
            )

        # Update draft status
        draft.status = DraftStatus.APPROVED.value
        draft.updated_at = datetime.now(timezone.utc)

        # 2. Update approval audit record
        await self.outreach_repo.update_approval(
            organization_id=organization_id,
            draft_id=draft_id,
            status="APPROVED",
            reviewed_by=reviewed_by,
            decision_reason=decision_reason,
        )

        # 3. Update lead status in CRM
        lead = await self.lead_repo.get_by_id(organization_id, draft.lead_id)
        if lead:
            lead.status = LeadStatus.APPROVED.value
            lead.updated_at = datetime.now(timezone.utc)

        # 4. Emit event
        await EventDispatcher.emit(
            event_type="lead.outreach.approved",
            org_id=organization_id,
            lead_id=draft.lead_id,
            payload={
                "draft_id": str(draft.id),
                "channel": draft.channel,
                "reviewed_by": reviewed_by,
                "decision_reason": decision_reason,
            },
        )

        await self.session.commit()
        return draft

    async def reject_draft(
        self,
        organization_id: uuid.UUID,
        draft_id: uuid.UUID,
        reviewed_by: Optional[str] = "SAHIL",
        decision_reason: str = "Rejected draft.",
    ) -> Optional[OutreachDraft]:
        draft = await self.outreach_repo.get_draft_by_id(organization_id, draft_id)
        if not draft:
            return None

        # Cannot reject already sent or executed drafts
        if draft.status in (DraftStatus.SENT.value, DraftStatus.SUPERSEDED.value):
            raise ValueError(
                f"Illegal state transition: cannot reject draft in terminal/executed state '{draft.status}'."
            )

        draft.status = DraftStatus.REJECTED.value
        draft.updated_at = datetime.now(timezone.utc)

        await self.outreach_repo.update_approval(
            organization_id=organization_id,
            draft_id=draft_id,
            status="REJECTED",
            reviewed_by=reviewed_by,
            decision_reason=decision_reason,
        )

        await EventDispatcher.emit(
            event_type="lead.outreach.rejected",
            org_id=organization_id,
            lead_id=draft.lead_id,
            payload={
                "draft_id": str(draft.id),
                "reviewed_by": reviewed_by,
                "reason": decision_reason,
            },
        )

        await self.session.commit()
        return draft

    async def regenerate_draft(
        self,
        organization_id: uuid.UUID,
        draft_id: uuid.UUID,
        preferences: Optional[List[str]] = None,
        target_channel: Optional[OutreachChannel] = None,
    ) -> Optional[OutreachDraft]:
        old_draft = await self.outreach_repo.get_draft_by_id(organization_id, draft_id)
        if not old_draft:
            return None

        channel = target_channel or OutreachChannel(old_draft.channel)

        # Mark old draft as SUPERSEDED
        old_draft.status = DraftStatus.SUPERSEDED.value
        old_draft.updated_at = datetime.now(timezone.utc)

        # Generate new variants with requested preferences
        drafts = await self.generate_outreach(
            organization_id=organization_id,
            lead_id=old_draft.lead_id,
            channel=channel,
            variant_count=1,
            preferences=preferences,
            override_duplicate=True,  # Regeneration is user-instructed
        )

        new_draft = drafts[0] if drafts else None
        if new_draft:
            await EventDispatcher.emit(
                event_type="lead.outreach.regenerated",
                org_id=organization_id,
                lead_id=old_draft.lead_id,
                payload={
                    "old_draft_id": str(old_draft.id),
                    "new_draft_id": str(new_draft.id),
                    "preferences": preferences or [],
                },
            )

        return new_draft

    async def get_outreach_history(
        self,
        organization_id: uuid.UUID,
        lead_id: uuid.UUID,
    ) -> Dict[str, Any]:
        drafts = await self.outreach_repo.list_drafts_by_lead(organization_id, lead_id)
        approvals = await self.outreach_repo.list_approvals_by_lead(organization_id, lead_id)
        attempts = await self.outreach_repo.list_attempts_by_lead(organization_id, lead_id)
        return {
            "lead_id": lead_id,
            "drafts": drafts,
            "approvals": approvals,
            "attempts": attempts,
        }
