import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.agents.conversation.conversation_engine import ConversationEngine
from services.api.app.agents.conversation.message_analyzer import ReplyMessageAnalyzer
from services.api.app.api.v1.dependencies.auth import get_current_org_id
from services.api.app.core.database import get_db
from services.api.app.repositories.conversation import ConversationRepository
from services.api.app.schemas.conversation import (
    ConversationAnalysisResponse,
    ConversationMessageIngestRequest,
    ConversationMessageResponse,
    ConversationReplyApprovalResponse,
    ConversationReplyApproveRequest,
    ConversationReplyDraftResponse,
    ConversationReplyGenerateRequest,
    ConversationReplyRejectRequest,
    ConversationSendRequest,
    ConversationSendResponse,
    ConversationThreadCreate,
    ConversationThreadResponse,
)
from services.api.app.services.conversation_memory_service import ConversationMemoryService
from services.api.app.services.conversation_service import ConversationService
from services.api.app.services.reply_service import ReplyService

router = APIRouter(tags=["Conversations"])


# --- Lead Conversation Endpoints ---

@router.post("/leads/{lead_id}/conversations", response_model=ConversationThreadResponse, status_code=status.HTTP_201_CREATED)
async def create_or_get_lead_conversation(
    lead_id: uuid.UUID,
    data: Optional[ConversationThreadCreate] = None,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> ConversationThreadResponse:
    service = ConversationService(db)
    channel = data.channel if data else "INSTAGRAM_DM"
    ext_ref = data.external_thread_ref if data else None

    thread = await service.get_or_create_thread(
        organization_id=org_id,
        lead_id=lead_id,
        channel=channel,
        external_thread_ref=ext_ref,
    )
    return ConversationThreadResponse.model_validate(thread)


@router.get("/leads/{lead_id}/conversations", response_model=List[ConversationThreadResponse])
async def list_lead_conversations(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> List[ConversationThreadResponse]:
    repo = ConversationRepository(db)
    threads = await repo.list_threads_by_lead(org_id, lead_id)
    return [ConversationThreadResponse.model_validate(t) for t in threads]


# --- Thread Core Endpoints ---

@router.get("/conversations/{thread_id}", response_model=ConversationThreadResponse)
async def get_conversation_thread(
    thread_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> ConversationThreadResponse:
    repo = ConversationRepository(db)
    thread = await repo.get_thread_by_id(org_id, thread_id)
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation thread not found")
    return ConversationThreadResponse.model_validate(thread)


@router.get("/conversations/{thread_id}/messages", response_model=List[ConversationMessageResponse])
async def list_conversation_messages(
    thread_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> List[ConversationMessageResponse]:
    repo = ConversationRepository(db)
    # verify thread exists for tenant
    thread = await repo.get_thread_by_id(org_id, thread_id)
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation thread not found")

    messages = await repo.list_messages_by_thread(org_id, thread_id)
    return [ConversationMessageResponse.model_validate(m) for m in messages]


@router.post("/conversations/{thread_id}/messages/ingest", response_model=ConversationMessageResponse, status_code=status.HTTP_201_CREATED)
async def ingest_conversation_message(
    thread_id: uuid.UUID,
    data: ConversationMessageIngestRequest,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> ConversationMessageResponse:
    service = ConversationService(db)
    msg, _ = await service.ingest_message(
        organization_id=org_id,
        thread_id=thread_id,
        content=data.content,
        external_message_ref=data.external_message_ref,
        source_url=data.source_url,
        author_type=data.author_type,
        direction=data.direction,
    )
    return ConversationMessageResponse.model_validate(msg)


@router.post("/conversations/{thread_id}/analyze", response_model=ConversationAnalysisResponse)
async def analyze_conversation_thread(
    thread_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> ConversationAnalysisResponse:
    repo = ConversationRepository(db)
    thread = await repo.get_thread_by_id(org_id, thread_id)
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation thread not found")

    messages = await repo.list_messages_by_thread(org_id, thread_id)
    latest_content = messages[-1].content if messages else "No messages"

    mem_service = ConversationMemoryService(db)
    context = await mem_service.build_context(org_id, thread)

    analysis = ConversationEngine.process_inbound_message(
        raw_message=latest_content,
        channel=thread.channel,
        context=context,
    )

    return ConversationAnalysisResponse(
        thread_id=thread.id,
        intent=analysis.intent.intent.value,
        confidence=analysis.intent.confidence,
        evidence=analysis.intent.evidence,
        objection_detected=analysis.objection.objection_type if analysis.objection else None,
        sales_stage=thread.sales_stage,
        recommended_objective=analysis.strategy.objective.value,
        rolling_summary=analysis.updated_summary,
    )


# --- Reply Draft & Approval Endpoints ---

@router.post("/conversations/{thread_id}/reply/generate", response_model=List[ConversationReplyDraftResponse], status_code=status.HTTP_201_CREATED)
async def generate_conversation_replies(
    thread_id: uuid.UUID,
    data: Optional[ConversationReplyGenerateRequest] = None,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> List[ConversationReplyDraftResponse]:
    reply_service = ReplyService(db)
    in_reply_to = data.in_reply_to_message_id if data else None
    drafts = await reply_service.generate_replies(
        organization_id=org_id,
        thread_id=thread_id,
        in_reply_to_message_id=in_reply_to,
    )
    return [ConversationReplyDraftResponse.model_validate(d) for d in drafts]


@router.get("/conversations/{thread_id}/replies", response_model=List[ConversationReplyDraftResponse])
async def list_conversation_replies(
    thread_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> List[ConversationReplyDraftResponse]:
    repo = ConversationRepository(db)
    # verify thread
    thread = await repo.get_thread_by_id(org_id, thread_id)
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation thread not found")

    replies = await repo.list_replies_by_thread(org_id, thread_id)
    return [ConversationReplyDraftResponse.model_validate(r) for r in replies]


@router.post("/conversations/{thread_id}/replies/{reply_id}/validate")
async def validate_conversation_reply(
    thread_id: uuid.UUID,
    reply_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    repo = ConversationRepository(db)
    reply = await repo.get_reply_draft_by_id(org_id, reply_id)
    if not reply or reply.thread_id != thread_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reply draft not found")

    thread = await repo.get_thread_by_id(org_id, thread_id)
    val_res = ReplyMessageAnalyzer.analyze(
        reply_body=reply.body,
        channel=thread.channel if thread else "INSTAGRAM_DM",
        prospect_name="Prospect",
        service_name="Custom Web Development",
        intent_name="QUESTION",
    )
    return val_res.model_dump()


@router.post("/conversations/{thread_id}/replies/{reply_id}/approve", response_model=ConversationReplyDraftResponse)
async def approve_conversation_reply(
    thread_id: uuid.UUID,
    reply_id: uuid.UUID,
    data: Optional[ConversationReplyApproveRequest] = None,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> ConversationReplyDraftResponse:
    reply_service = ReplyService(db)
    reviewer = data.reviewer_id if data else "Sahil"
    reason = data.decision_reason if data else "Approved by user"
    draft = await reply_service.approve_reply(
        organization_id=org_id,
        thread_id=thread_id,
        reply_id=reply_id,
        reviewer_id=reviewer,
        decision_reason=reason,
    )
    return ConversationReplyDraftResponse.model_validate(draft)


@router.post("/conversations/{thread_id}/replies/{reply_id}/reject", response_model=ConversationReplyDraftResponse)
async def reject_conversation_reply(
    thread_id: uuid.UUID,
    reply_id: uuid.UUID,
    data: ConversationReplyRejectRequest,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> ConversationReplyDraftResponse:
    reply_service = ReplyService(db)
    draft = await reply_service.reject_reply(
        organization_id=org_id,
        thread_id=thread_id,
        reply_id=reply_id,
        reviewer_id=data.reviewer_id,
        rejection_reason=data.rejection_reason,
    )
    return ConversationReplyDraftResponse.model_validate(draft)


@router.post("/conversations/{thread_id}/replies/{reply_id}/send", response_model=ConversationSendResponse)
async def send_conversation_reply(
    thread_id: uuid.UUID,
    reply_id: uuid.UUID,
    data: ConversationSendRequest,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> ConversationSendResponse:
    reply_service = ReplyService(db)
    res = await reply_service.send_reply_via_browser(
        organization_id=org_id,
        thread_id=thread_id,
        reply_id=reply_id,
        session_id=data.session_id,
    )
    return ConversationSendResponse(
        success=res["success"],
        status=res["status"],
        reply_id=reply_id,
        thread_id=thread_id,
        detail=res["detail"],
    )


@router.post("/conversations/{thread_id}/close", response_model=ConversationThreadResponse)
async def close_conversation_thread(
    thread_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> ConversationThreadResponse:
    service = ConversationService(db)
    thread = await service.close_thread(
        organization_id=org_id,
        thread_id=thread_id,
        reason="Closed by user request",
    )
    return ConversationThreadResponse.model_validate(thread)
