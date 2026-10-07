import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from services.api.app.models.outreach import (
    OutreachApproval,
    OutreachAttempt,
    OutreachCampaign,
    OutreachDraft,
    OutreachEvidence,
)
from packages.shared_types.outreach import DraftStatus


class OutreachRepository:
    """Repository handling all database persistence for outreach with strict tenant isolation."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_campaign(
        self,
        organization_id: uuid.UUID,
        name: str,
        channel: str,
        status: str = "ACTIVE",
    ) -> OutreachCampaign:
        campaign = OutreachCampaign(
            organization_id=organization_id,
            name=name,
            channel=channel,
            status=status,
        )
        self.session.add(campaign)
        await self.session.flush()
        return campaign

    async def create_draft(
        self,
        organization_id: uuid.UUID,
        lead_id: uuid.UUID,
        channel: str,
        variant: str,
        body: str,
        angle: str,
        recommended_service: str,
        quality_score: int,
        confidence: float,
        status: str,
        personalization_level: str = "DEEP",
        subject: Optional[str] = None,
        cta_text: Optional[str] = None,
        cta_category: Optional[str] = None,
        suggested_follow_up_at: Optional[datetime] = None,
        follow_up_reason: Optional[str] = None,
        campaign_id: Optional[uuid.UUID] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
    ) -> OutreachDraft:
        draft = OutreachDraft(
            organization_id=organization_id,
            lead_id=lead_id,
            campaign_id=campaign_id,
            channel=channel,
            variant=variant,
            subject=subject,
            body=body,
            personalization_level=personalization_level,
            angle=angle,
            recommended_service=recommended_service,
            quality_score=quality_score,
            confidence=confidence,
            status=status,
            cta_text=cta_text,
            cta_category=cta_category,
            suggested_follow_up_at=suggested_follow_up_at,
            follow_up_reason=follow_up_reason,
            metadata_json=metadata_json,
        )
        self.session.add(draft)
        await self.session.flush()
        return draft

    async def add_evidence(
        self,
        organization_id: uuid.UUID,
        draft_id: uuid.UUID,
        claim: str,
        evidence_text: str,
        evidence_type: str,
        source_url: Optional[str] = None,
        confidence: float = 0.9,
    ) -> OutreachEvidence:
        evidence = OutreachEvidence(
            organization_id=organization_id,
            draft_id=draft_id,
            claim=claim,
            source_url=source_url,
            evidence_text=evidence_text,
            evidence_type=evidence_type,
            confidence=confidence,
        )
        self.session.add(evidence)
        await self.session.flush()
        return evidence

    async def get_draft_by_id(
        self,
        organization_id: uuid.UUID,
        draft_id: uuid.UUID,
    ) -> Optional[OutreachDraft]:
        stmt = (
            select(OutreachDraft)
            .where(
                OutreachDraft.id == draft_id,
                OutreachDraft.organization_id == organization_id,
            )
            .options(
                selectinload(OutreachDraft.evidences),
                selectinload(OutreachDraft.approvals),
                selectinload(OutreachDraft.attempts),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_draft(
        self,
        organization_id: uuid.UUID,
        draft_id: uuid.UUID,
    ) -> Optional[OutreachDraft]:
        return await self.get_draft_by_id(organization_id, draft_id)

    async def list_drafts_by_lead(
        self,
        organization_id: uuid.UUID,
        lead_id: uuid.UUID,
    ) -> List[OutreachDraft]:
        stmt = (
            select(OutreachDraft)
            .where(
                OutreachDraft.lead_id == lead_id,
                OutreachDraft.organization_id == organization_id,
            )
            .options(
                selectinload(OutreachDraft.evidences),
                selectinload(OutreachDraft.approvals),
            )
            .order_by(OutreachDraft.created_at.desc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def update_draft_status(
        self,
        organization_id: uuid.UUID,
        draft_id: uuid.UUID,
        status: str,
        quality_score: Optional[int] = None,
    ) -> Optional[OutreachDraft]:
        draft = await self.get_draft_by_id(organization_id, draft_id)
        if not draft:
            return None
        draft.status = status
        if quality_score is not None:
            draft.quality_score = quality_score
        draft.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return draft

    async def supersede_previous_drafts(
        self,
        organization_id: uuid.UUID,
        lead_id: uuid.UUID,
        channel: Optional[str] = None,
    ) -> int:
        stmt = (
            update(OutreachDraft)
            .where(
                OutreachDraft.organization_id == organization_id,
                OutreachDraft.lead_id == lead_id,
                OutreachDraft.status.in_([
                    DraftStatus.DRAFT.value,
                    DraftStatus.VALIDATING.value,
                    DraftStatus.NEEDS_REVIEW.value,
                    DraftStatus.READY_FOR_APPROVAL.value,
                ]),
            )
        )
        if channel:
            stmt = stmt.where(OutreachDraft.channel == channel)
        stmt = stmt.values(
            status=DraftStatus.SUPERSEDED.value,
            updated_at=datetime.now(timezone.utc),
        )
        res = await self.session.execute(stmt)
        await self.session.flush()
        return res.rowcount

    async def create_approval(
        self,
        organization_id: uuid.UUID,
        lead_id: uuid.UUID,
        draft_id: uuid.UUID,
        channel: str,
        requested_by: Optional[str] = "SYSTEM",
    ) -> OutreachApproval:
        approval = OutreachApproval(
            organization_id=organization_id,
            lead_id=lead_id,
            draft_id=draft_id,
            channel=channel,
            requested_by=requested_by,
            status="PENDING",
        )
        self.session.add(approval)
        await self.session.flush()
        return approval

    async def update_approval(
        self,
        organization_id: uuid.UUID,
        draft_id: uuid.UUID,
        status: str,
        reviewed_by: Optional[str],
        decision_reason: Optional[str],
    ) -> Optional[OutreachApproval]:
        stmt = (
            select(OutreachApproval)
            .where(
                OutreachApproval.draft_id == draft_id,
                OutreachApproval.organization_id == organization_id,
            )
            .order_by(OutreachApproval.created_at.desc())
        )
        res = await self.session.execute(stmt)
        approval = res.scalar_one_or_none()
        if not approval:
            # Create one if not existing
            draft = await self.get_draft_by_id(organization_id, draft_id)
            if not draft:
                return None
            approval = OutreachApproval(
                organization_id=organization_id,
                lead_id=draft.lead_id,
                draft_id=draft_id,
                channel=draft.channel,
                requested_by="SYSTEM",
            )
            self.session.add(approval)

        approval.status = status
        approval.reviewed_by = reviewed_by
        approval.reviewed_at = datetime.now(timezone.utc)
        approval.decision_reason = decision_reason
        await self.session.flush()
        return approval

    async def record_attempt(
        self,
        organization_id: Optional[uuid.UUID] = None,
        lead_id: Optional[uuid.UUID] = None,
        channel: str = "INSTAGRAM_DM",
        status: str = "SENT",
        recipient: Optional[str] = None,
        draft_id: Optional[uuid.UUID] = None,
        reason: Optional[str] = None,
        org_id: Optional[uuid.UUID] = None,
    ) -> OutreachAttempt:
        final_org_id = organization_id or org_id
        if not final_org_id or not lead_id:
            raise ValueError("organization_id and lead_id are required")
        attempt = OutreachAttempt(
            organization_id=final_org_id,
            lead_id=lead_id,
            draft_id=draft_id,
            channel=channel,
            recipient=recipient,
            status=status,
            reason=reason,
        )
        self.session.add(attempt)
        await self.session.flush()
        return attempt

    async def list_approvals_by_lead(
        self,
        organization_id: uuid.UUID,
        lead_id: uuid.UUID,
    ) -> List[OutreachApproval]:
        stmt = (
            select(OutreachApproval)
            .where(
                OutreachApproval.lead_id == lead_id,
                OutreachApproval.organization_id == organization_id,
            )
            .order_by(OutreachApproval.created_at.desc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def list_attempts_by_lead(
        self,
        organization_id: uuid.UUID,
        lead_id: uuid.UUID,
    ) -> List[OutreachAttempt]:
        stmt = (
            select(OutreachAttempt)
            .where(
                OutreachAttempt.lead_id == lead_id,
                OutreachAttempt.organization_id == organization_id,
            )
            .order_by(OutreachAttempt.created_at.desc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_attempts_for_lead(
        self,
        organization_id: uuid.UUID,
        lead_id: uuid.UUID,
    ) -> List[OutreachAttempt]:
        return await self.list_attempts_by_lead(organization_id, lead_id)

