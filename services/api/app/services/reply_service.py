import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared_types.browser_protocol import (
    BrowserCommand,
    BrowserCommandType,
    CommandExecutionStatus,
)
from packages.shared_types.conversation import (
    MessageAuthorType,
    MessageDeliveryStatus,
    MessageDirection,
    ProspectIntent,
    ReplyApprovalStatus,
    SalesStage,
    ThreadStatus,
)
from services.api.app.agents.browser.gateway import browser_gateway
from services.api.app.agents.conversation.conversation_engine import ConversationEngine
from services.api.app.models.conversation import (
    ConversationApproval,
    ConversationMessage,
    ConversationReplyDraft,
    ConversationThread,
)
from services.api.app.repositories.conversation import ConversationRepository
from services.api.app.services.conversation_memory_service import ConversationMemoryService
from services.api.app.services.event_dispatcher import EventDispatcher


class ReplyService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ConversationRepository(session)
        self.memory_service = ConversationMemoryService(session)

    async def generate_replies(
        self,
        organization_id: uuid.UUID,
        thread_id: uuid.UUID,
        in_reply_to_message_id: Optional[uuid.UUID] = None,
    ) -> List[ConversationReplyDraft]:
        thread = await self.repo.get_thread_by_id(organization_id, thread_id)
        if not thread:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation thread not found")

        # Get latest message
        messages = await self.repo.list_messages_by_thread(organization_id, thread_id)
        if not messages:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No messages in thread to reply to")

        latest_msg = messages[-1]
        target_msg_id = in_reply_to_message_id or latest_msg.id

        # Build context
        context = await self.memory_service.build_context(organization_id, thread)

        # Run conversation engine
        analysis = ConversationEngine.process_inbound_message(
            raw_message=latest_msg.content,
            channel=thread.channel,
            context=context,
        )

        created_drafts: List[ConversationReplyDraft] = []
        for variant in analysis.reply_variants:
            status_val = "READY_FOR_APPROVAL" if variant.quality_score >= 75 and not variant.risk_flags else "NEEDS_REGENERATION"
            draft = await self.repo.create_reply_draft(
                organization_id=organization_id,
                thread_id=thread_id,
                body=variant.body,
                variant=variant.variant,
                objective=variant.objective,
                quality_score=variant.quality_score,
                confidence=variant.confidence,
                status=status_val,
                in_reply_to_message_id=target_msg_id,
                evidence_text=variant.evidence,
                risk_flags=variant.risk_flags,
                requires_human_approval=True,
                metadata_json={
                    "recommended_cta": analysis.strategy.recommended_cta,
                    "intent": analysis.intent.intent.value,
                },
            )
            created_drafts.append(draft)

            if status_val == "READY_FOR_APPROVAL":
                # Create pending approval
                await self.repo.create_approval(
                    organization_id=organization_id,
                    thread_id=thread_id,
                    reply_id=draft.id,
                    status=ReplyApprovalStatus.PENDING.value,
                )
                await EventDispatcher.dispatch(
                    event_type="conversation.reply.ready_for_approval",
                    data={
                        "thread_id": str(thread_id),
                        "reply_id": str(draft.id),
                        "variant": draft.variant,
                        "quality_score": draft.quality_score,
                    },
                    organization_id=organization_id,
                )

        await EventDispatcher.dispatch(
            event_type="conversation.reply.drafted",
            data={
                "thread_id": str(thread_id),
                "drafts_count": len(created_drafts),
            },
            organization_id=organization_id,
        )

        return created_drafts

    async def approve_reply(
        self,
        organization_id: uuid.UUID,
        thread_id: uuid.UUID,
        reply_id: uuid.UUID,
        reviewer_id: str = "Sahil",
        decision_reason: Optional[str] = None,
    ) -> ConversationReplyDraft:
        draft = await self.repo.get_reply_draft_by_id(organization_id, reply_id)
        if not draft or draft.thread_id != thread_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reply draft not found")

        approval = await self.repo.get_approval_by_reply_id(organization_id, reply_id)
        if not approval:
            approval = await self.repo.create_approval(
                organization_id=organization_id,
                thread_id=thread_id,
                reply_id=reply_id,
                status=ReplyApprovalStatus.PENDING.value,
            )

        approval.status = ReplyApprovalStatus.APPROVED.value
        approval.reviewer_id = reviewer_id
        approval.reviewed_at = datetime.now(timezone.utc)
        approval.decision_reason = decision_reason or "Approved for transmission"

        draft.status = "APPROVED"
        self.session.add(approval)
        self.session.add(draft)
        await self.session.commit()
        await self.session.refresh(draft)

        await EventDispatcher.dispatch(
            event_type="conversation.reply.approved",
            data={
                "thread_id": str(thread_id),
                "reply_id": str(reply_id),
                "reviewer_id": reviewer_id,
            },
            organization_id=organization_id,
        )
        return draft

    async def reject_reply(
        self,
        organization_id: uuid.UUID,
        thread_id: uuid.UUID,
        reply_id: uuid.UUID,
        reviewer_id: str = "Sahil",
        rejection_reason: str = "Rejected by reviewer",
    ) -> ConversationReplyDraft:
        draft = await self.repo.get_reply_draft_by_id(organization_id, reply_id)
        if not draft or draft.thread_id != thread_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reply draft not found")

        approval = await self.repo.get_approval_by_reply_id(organization_id, reply_id)
        if approval:
            approval.status = ReplyApprovalStatus.REJECTED.value
            approval.reviewer_id = reviewer_id
            approval.reviewed_at = datetime.now(timezone.utc)
            approval.decision_reason = rejection_reason
            self.session.add(approval)

        draft.status = "REJECTED"
        self.session.add(draft)
        await self.session.commit()
        await self.session.refresh(draft)

        await EventDispatcher.dispatch(
            event_type="conversation.reply.rejected",
            data={
                "thread_id": str(thread_id),
                "reply_id": str(reply_id),
                "rejection_reason": rejection_reason,
            },
            organization_id=organization_id,
        )
        return draft

    async def send_reply_via_browser(
        self,
        organization_id: uuid.UUID,
        thread_id: uuid.UUID,
        reply_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """
        Executes an approved reply draft via the connected Chrome browser extension.
        Enforces human approval check, recipient validation, wrong-thread protection,
        and uncertain delivery protection.
        """
        draft = await self.repo.get_reply_draft_by_id(organization_id, reply_id)
        if not draft or draft.thread_id != thread_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reply draft not found")

        # 1. Approval Gate
        if draft.status != "APPROVED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Reply cannot be sent: status is '{draft.status}', must be APPROVED",
            )

        thread = await self.repo.get_thread_by_id(organization_id, thread_id)
        if not thread:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation thread not found")

        # 2. Check Extension Connection
        if not browser_gateway.is_connected(session_id):
            raise HTTPException(
                status_code=status.HTTP_412_PRECONDITION_FAILED,
                detail=f"Browser session {session_id} is not connected to Chrome extension",
            )

        # 3. Wrong Thread / Context Protection
        context = await self.memory_service.build_context(organization_id, thread)
        recipient = context.contact_handle or "Prospect"

        command = BrowserCommand(
            session_id=session_id,
            type=BrowserCommandType.EXECUTE_APPROVED_OUTREACH,
            payload={
                "draft_id": str(draft.id),
                "thread_id": str(thread.id),
                "lead_id": str(thread.lead_id),
                "channel": thread.channel,
                "recipient": recipient,
                "body": draft.body,
                "variant": draft.variant,
            },
        )

        # 4. Dispatch Command to Extension
        result = await browser_gateway.send_command(command, timeout_seconds=30.0)

        # 5. Evaluate Result
        if result.status == CommandExecutionStatus.DELIVERY_UNKNOWN:
            # Uncertain delivery protection: record delivery state without automatic retry
            draft.status = "NEEDS_REVIEW"
            self.session.add(draft)
            await self.session.commit()

            await EventDispatcher.dispatch(
                event_type="conversation.delivery.unknown",
                data={
                    "thread_id": str(thread_id),
                    "reply_id": str(reply_id),
                    "session_id": str(session_id),
                    "detail": "DOM state changed but external delivery could not be confirmed",
                },
                organization_id=organization_id,
            )
            return {
                "success": False,
                "status": "DELIVERY_UNKNOWN",
                "reply_id": reply_id,
                "thread_id": thread_id,
                "detail": "Message delivery could not be verified with certainty. Human review required; automated retry blocked.",
            }

        elif result.success:
            draft.status = "SENT"
            self.session.add(draft)

            # Record outbound message in conversation thread
            await self.repo.create_message(
                organization_id=organization_id,
                thread_id=thread_id,
                direction=MessageDirection.OUTBOUND.value,
                author_type=MessageAuthorType.AGENT.value,
                content=draft.body,
                sanitized_content=draft.body,
                delivery_status=MessageDeliveryStatus.SENT.value,
                evidence=draft.evidence_text,
            )

            # Update thread state
            thread.status = ThreadStatus.WAITING_FOR_REPLY.value
            thread.last_message_at = datetime.now(timezone.utc)
            self.session.add(thread)
            await self.session.commit()

            await EventDispatcher.dispatch(
                event_type="conversation.reply.sent",
                data={
                    "thread_id": str(thread_id),
                    "reply_id": str(reply_id),
                    "channel": thread.channel,
                    "recipient": recipient,
                },
                organization_id=organization_id,
            )

            return {
                "success": True,
                "status": "SENT",
                "reply_id": reply_id,
                "thread_id": thread_id,
                "detail": "Reply message successfully transmitted via Chrome browser extension",
            }

        else:
            draft.status = "FAILED"
            self.session.add(draft)
            await self.session.commit()
            return {
                "success": False,
                "status": "FAILED",
                "reply_id": reply_id,
                "thread_id": thread_id,
                "detail": result.error or "Failed to execute message in browser",
            }
