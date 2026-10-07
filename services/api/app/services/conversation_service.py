import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared_types.conversation import (
    MessageAuthorType,
    MessageDeliveryStatus,
    MessageDirection,
    ProspectIntent,
    SalesStage,
    ThreadStatus,
)
from services.api.app.agents.conversation.conversation_engine import ConversationEngine
from services.api.app.agents.conversation.validators import sanitize_inbound_message
from services.api.app.models.conversation import ConversationMessage, ConversationThread
from services.api.app.repositories.conversation import ConversationRepository
from services.api.app.services.conversation_memory_service import ConversationMemoryService
from services.api.app.services.event_dispatcher import EventDispatcher
from services.api.app.services.sales_stage_service import SalesStageService


class ConversationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ConversationRepository(session)
        self.memory_service = ConversationMemoryService(session)

    async def get_or_create_thread(
        self,
        organization_id: uuid.UUID,
        lead_id: uuid.UUID,
        channel: str = "INSTAGRAM_DM",
        external_thread_ref: Optional[str] = None,
    ) -> ConversationThread:
        existing = await self.repo.get_thread_by_lead_and_channel(organization_id, lead_id, channel)
        if existing:
            return existing

        thread = await self.repo.create_thread(
            organization_id=organization_id,
            lead_id=lead_id,
            channel=channel,
            external_thread_ref=external_thread_ref,
            status=ThreadStatus.ACTIVE.value,
            sales_stage=SalesStage.CONTACTED.value,
        )

        await EventDispatcher.dispatch(
            event_type="conversation.created",
            data={
                "thread_id": str(thread.id),
                "lead_id": str(lead_id),
                "channel": channel,
            },
            organization_id=organization_id,
        )
        return thread

    async def ingest_message(
        self,
        organization_id: uuid.UUID,
        thread_id: uuid.UUID,
        content: str,
        external_message_ref: Optional[str] = None,
        source_url: Optional[str] = None,
        author_type: str = MessageAuthorType.PROSPECT.value,
        direction: str = MessageDirection.INBOUND.value,
    ) -> Tuple[ConversationMessage, ConversationThread]:
        thread = await self.repo.get_thread_by_id(organization_id, thread_id)
        if not thread:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation thread not found")

        # 1. Idempotency Check (by external_message_ref)
        if external_message_ref:
            existing = await self.repo.get_message_by_external_ref(organization_id, external_message_ref)
            if existing:
                return existing, thread

        # 2. Content Deduplication Check (same thread, identical content within latest messages)
        recent_msgs = await self.repo.list_messages_by_thread(organization_id, thread_id)
        if recent_msgs:
            last = recent_msgs[-1]
            if last.content.strip() == content.strip() and last.author_type == author_type:
                # Duplicate submission
                return last, thread

        # 3. Sanitize Content & Prompt Injection Defense
        sanitized = sanitize_inbound_message(content)

        # 4. Save Inbound Message
        msg = await self.repo.create_message(
            organization_id=organization_id,
            thread_id=thread_id,
            direction=direction,
            author_type=author_type,
            content=content,
            sanitized_content=sanitized,
            source_url=source_url,
            external_message_ref=external_message_ref,
            delivery_status=MessageDeliveryStatus.RECEIVED.value,
        )

        await EventDispatcher.dispatch(
            event_type="conversation.message.received",
            data={
                "thread_id": str(thread_id),
                "message_id": str(msg.id),
                "direction": direction,
                "author_type": author_type,
            },
            organization_id=organization_id,
        )

        # 5. Process Inbound Prospect Logic
        if direction == MessageDirection.INBOUND.value:
            context = await self.memory_service.build_context(organization_id, thread)
            analysis = ConversationEngine.process_inbound_message(
                raw_message=sanitized,
                channel=thread.channel,
                context=context,
            )

            # Update thread memory & status
            thread.current_intent = analysis.intent.intent.value
            thread.summary = analysis.updated_summary
            thread.last_message_at = datetime.now(timezone.utc)
            thread.status = ThreadStatus.ACTIVE.value

            # Update sales stage deterministically
            new_stage = SalesStageService.evaluate_next_stage(
                current_stage_str=thread.sales_stage,
                intent=analysis.intent.intent,
            )
            old_stage = thread.sales_stage
            thread.sales_stage = new_stage

            await self.repo.update_thread(thread)

            await EventDispatcher.dispatch(
                event_type="conversation.intent.detected",
                data={
                    "thread_id": str(thread_id),
                    "intent": analysis.intent.intent.value,
                    "confidence": analysis.intent.confidence,
                    "evidence": analysis.intent.evidence,
                },
                organization_id=organization_id,
            )

            if new_stage != old_stage:
                await EventDispatcher.dispatch(
                    event_type="conversation.stage.updated",
                    data={
                        "thread_id": str(thread_id),
                        "old_stage": old_stage,
                        "new_stage": new_stage,
                    },
                    organization_id=organization_id,
                )

        return msg, thread

    async def close_thread(
        self,
        organization_id: uuid.UUID,
        thread_id: uuid.UUID,
        reason: Optional[str] = None,
    ) -> ConversationThread:
        thread = await self.repo.get_thread_by_id(organization_id, thread_id)
        if not thread:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation thread not found")

        thread.status = ThreadStatus.CLOSED.value
        await self.repo.update_thread(thread)

        await EventDispatcher.dispatch(
            event_type="conversation.closed",
            data={
                "thread_id": str(thread_id),
                "reason": reason or "Closed by user",
            },
            organization_id=organization_id,
        )
        return thread
