import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from packages.shared_types.conversation import (
    MessageAuthorType,
    MessageDeliveryStatus,
    MessageDirection,
    ReplyApprovalStatus,
    SalesStage,
    ThreadStatus,
)
from services.api.app.models.conversation import (
    ConversationApproval,
    ConversationMessage,
    ConversationReplyDraft,
    ConversationThread,
)


class ConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- Thread Operations ---

    async def create_thread(
        self,
        organization_id: uuid.UUID,
        lead_id: uuid.UUID,
        channel: str = "INSTAGRAM_DM",
        external_thread_ref: Optional[str] = None,
        status: str = ThreadStatus.ACTIVE.value,
        sales_stage: str = SalesStage.CONTACTED.value,
        metadata_json: Optional[Dict[str, Any]] = None,
    ) -> ConversationThread:
        thread = ConversationThread(
            organization_id=organization_id,
            lead_id=lead_id,
            channel=channel,
            external_thread_ref=external_thread_ref,
            status=status,
            sales_stage=sales_stage,
            metadata_json=metadata_json,
        )
        self.session.add(thread)
        await self.session.commit()
        await self.session.refresh(thread)
        return thread

    async def get_thread_by_id(
        self,
        organization_id: uuid.UUID,
        thread_id: uuid.UUID,
    ) -> Optional[ConversationThread]:
        stmt = (
            select(ConversationThread)
            .where(
                ConversationThread.id == thread_id,
                ConversationThread.organization_id == organization_id,
            )
            .options(
                selectinload(ConversationThread.messages),
                selectinload(ConversationThread.replies),
                selectinload(ConversationThread.approvals),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_thread_by_lead_and_channel(
        self,
        organization_id: uuid.UUID,
        lead_id: uuid.UUID,
        channel: str,
    ) -> Optional[ConversationThread]:
        stmt = (
            select(ConversationThread)
            .where(
                ConversationThread.organization_id == organization_id,
                ConversationThread.lead_id == lead_id,
                ConversationThread.channel == channel,
            )
            .order_by(desc(ConversationThread.created_at))
            .limit(1)
            .options(
                selectinload(ConversationThread.messages),
                selectinload(ConversationThread.replies),
                selectinload(ConversationThread.approvals),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_threads_by_lead(
        self,
        organization_id: uuid.UUID,
        lead_id: uuid.UUID,
    ) -> List[ConversationThread]:
        stmt = (
            select(ConversationThread)
            .where(
                ConversationThread.organization_id == organization_id,
                ConversationThread.lead_id == lead_id,
            )
            .order_by(desc(ConversationThread.updated_at))
            .options(selectinload(ConversationThread.messages))
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def update_thread(self, thread: ConversationThread) -> ConversationThread:
        thread.updated_at = datetime.now(timezone.utc)
        self.session.add(thread)
        await self.session.commit()
        await self.session.refresh(thread)
        return thread

    # --- Message Operations ---

    async def create_message(
        self,
        organization_id: uuid.UUID,
        thread_id: uuid.UUID,
        direction: str,
        author_type: str,
        content: str,
        sanitized_content: str,
        source_url: Optional[str] = None,
        external_message_ref: Optional[str] = None,
        delivery_status: str = MessageDeliveryStatus.RECEIVED.value,
        evidence: Optional[str] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
    ) -> ConversationMessage:
        msg = ConversationMessage(
            organization_id=organization_id,
            thread_id=thread_id,
            direction=direction,
            author_type=author_type,
            content=content,
            sanitized_content=sanitized_content,
            source_url=source_url,
            external_message_ref=external_message_ref,
            delivery_status=delivery_status,
            evidence=evidence,
            metadata_json=metadata_json,
        )
        self.session.add(msg)
        await self.session.commit()
        await self.session.refresh(msg)
        return msg

    async def get_message_by_external_ref(
        self,
        organization_id: uuid.UUID,
        external_ref: str,
    ) -> Optional[ConversationMessage]:
        stmt = (
            select(ConversationMessage)
            .where(
                ConversationMessage.organization_id == organization_id,
                ConversationMessage.external_message_ref == external_ref,
            )
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_messages_by_thread(
        self,
        organization_id: uuid.UUID,
        thread_id: uuid.UUID,
    ) -> List[ConversationMessage]:
        stmt = (
            select(ConversationMessage)
            .where(
                ConversationMessage.organization_id == organization_id,
                ConversationMessage.thread_id == thread_id,
            )
            .order_by(ConversationMessage.created_at.asc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # --- Reply Operations ---

    async def create_reply_draft(
        self,
        organization_id: uuid.UUID,
        thread_id: uuid.UUID,
        body: str,
        variant: str = "DIRECT",
        objective: str = "ANSWER",
        quality_score: int = 0,
        confidence: float = 0.0,
        status: str = "DRAFT",
        in_reply_to_message_id: Optional[uuid.UUID] = None,
        evidence_text: Optional[str] = None,
        risk_flags: Optional[List[str]] = None,
        requires_human_approval: bool = True,
        metadata_json: Optional[Dict[str, Any]] = None,
    ) -> ConversationReplyDraft:
        reply = ConversationReplyDraft(
            organization_id=organization_id,
            thread_id=thread_id,
            body=body,
            variant=variant,
            objective=objective,
            quality_score=quality_score,
            confidence=confidence,
            status=status,
            in_reply_to_message_id=in_reply_to_message_id,
            evidence_text=evidence_text,
            risk_flags=risk_flags,
            requires_human_approval=requires_human_approval,
            metadata_json=metadata_json,
        )
        self.session.add(reply)
        await self.session.commit()
        await self.session.refresh(reply)
        return reply

    async def get_reply_draft_by_id(
        self,
        organization_id: uuid.UUID,
        reply_id: uuid.UUID,
    ) -> Optional[ConversationReplyDraft]:
        stmt = (
            select(ConversationReplyDraft)
            .where(
                ConversationReplyDraft.id == reply_id,
                ConversationReplyDraft.organization_id == organization_id,
            )
            .options(selectinload(ConversationReplyDraft.approvals))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_replies_by_thread(
        self,
        organization_id: uuid.UUID,
        thread_id: uuid.UUID,
    ) -> List[ConversationReplyDraft]:
        stmt = (
            select(ConversationReplyDraft)
            .where(
                ConversationReplyDraft.organization_id == organization_id,
                ConversationReplyDraft.thread_id == thread_id,
            )
            .order_by(desc(ConversationReplyDraft.created_at))
            .options(selectinload(ConversationReplyDraft.approvals))
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # --- Approval Operations ---

    async def create_approval(
        self,
        organization_id: uuid.UUID,
        thread_id: uuid.UUID,
        reply_id: uuid.UUID,
        status: str = ReplyApprovalStatus.PENDING.value,
        reviewer_id: Optional[str] = None,
        decision_reason: Optional[str] = None,
    ) -> ConversationApproval:
        approval = ConversationApproval(
            organization_id=organization_id,
            thread_id=thread_id,
            reply_id=reply_id,
            status=status,
            reviewer_id=reviewer_id,
            decision_reason=decision_reason,
        )
        self.session.add(approval)
        await self.session.commit()
        await self.session.refresh(approval)
        return approval

    async def get_approval_by_reply_id(
        self,
        organization_id: uuid.UUID,
        reply_id: uuid.UUID,
    ) -> Optional[ConversationApproval]:
        stmt = (
            select(ConversationApproval)
            .where(
                ConversationApproval.organization_id == organization_id,
                ConversationApproval.reply_id == reply_id,
            )
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()
