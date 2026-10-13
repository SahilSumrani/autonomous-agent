import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.api.v1.dependencies.auth import get_current_org_id
from services.api.app.core.database import get_db
from services.api.app.schemas.outreach import (
    ApproveDraftRequest,
    GenerateOutreachRequest,
    OutreachApprovalResponse,
    OutreachAttemptResponse,
    OutreachDraftResponse,
    OutreachEvidenceResponse,
    OutreachHistoryResponse,
    RegenerateOutreachRequest,
    RejectDraftRequest,
    ValidationDetailResponse,
)
from services.api.app.services.outreach_service import (
    DuplicateOutreachBlockedError,
    OutreachService,
)

router = APIRouter(prefix="/leads", tags=["Outreach Intelligence"])


def _to_draft_response(d) -> OutreachDraftResponse:
    evidences = [
        OutreachEvidenceResponse(
            id=ev.id,
            draft_id=ev.draft_id,
            claim=ev.claim,
            source_url=ev.source_url,
            evidence_text=ev.evidence_text,
            evidence_type=ev.evidence_type,
            confidence=ev.confidence,
            created_at=ev.created_at,
        )
        for ev in (d.evidences or [])
    ]
    return OutreachDraftResponse(
        id=d.id,
        lead_id=d.lead_id,
        campaign_id=d.campaign_id,
        channel=d.channel,
        variant=d.variant,
        subject=d.subject,
        body=d.body,
        personalization_level=d.personalization_level,
        angle=d.angle,
        recommended_service=d.recommended_service,
        quality_score=d.quality_score,
        confidence=d.confidence,
        status=d.status,
        cta_text=d.cta_text,
        cta_category=d.cta_category,
        suggested_follow_up_at=d.suggested_follow_up_at,
        follow_up_reason=d.follow_up_reason,
        metadata_json=d.metadata_json,
        created_at=d.created_at,
        updated_at=d.updated_at,
        evidences=evidences,
    )


@router.post("/{lead_id}/outreach/generate", response_model=List[OutreachDraftResponse], status_code=status.HTTP_201_CREATED)
async def generate_lead_outreach(
    lead_id: uuid.UUID,
    data: Optional[GenerateOutreachRequest] = None,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> List[OutreachDraftResponse]:
    """Generates structured, evidence-backed outreach draft variants for a qualified lead."""
    service = OutreachService(db)
    channel = data.channel if data else None
    variant_count = data.variant_count if data else 3
    preferences = data.preferences if data else None
    override_dup = data.override_duplicate if data else False

    try:
        drafts = await service.generate_outreach(
            organization_id=org_id,
            lead_id=lead_id,
            channel=channel,
            variant_count=variant_count,
            preferences=preferences,
            override_duplicate=override_dup,
        )
        return [_to_draft_response(d) for d in drafts]
    except DuplicateOutreachBlockedError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Duplicate outreach blocked: {e}")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{lead_id}/outreach", response_model=List[OutreachDraftResponse])
async def list_lead_outreach(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> List[OutreachDraftResponse]:
    """Lists all outreach drafts generated for the specified lead."""
    service = OutreachService(db)
    drafts = await service.list_drafts(organization_id=org_id, lead_id=lead_id)
    return [_to_draft_response(d) for d in drafts]


@router.get("/{lead_id}/outreach/history", response_model=OutreachHistoryResponse)
async def get_outreach_history(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> OutreachHistoryResponse:
    """Returns the complete outreach history including drafts, approvals, and attempts."""
    service = OutreachService(db)
    history = await service.get_outreach_history(organization_id=org_id, lead_id=lead_id)

    drafts = [_to_draft_response(d) for d in history["drafts"]]
    approvals = [
        OutreachApprovalResponse(
            id=a.id,
            lead_id=a.lead_id,
            draft_id=a.draft_id,
            channel=a.channel,
            requested_by=a.requested_by,
            status=a.status,
            reviewed_by=a.reviewed_by,
            reviewed_at=a.reviewed_at,
            decision_reason=a.decision_reason,
            created_at=a.created_at,
        )
        for a in history["approvals"]
    ]
    attempts = [
        OutreachAttemptResponse(
            id=att.id,
            lead_id=att.lead_id,
            draft_id=att.draft_id,
            channel=att.channel,
            recipient=att.recipient,
            status=att.status,
            reason=att.reason,
            created_at=att.created_at,
        )
        for att in history["attempts"]
    ]

    return OutreachHistoryResponse(
        lead_id=lead_id,
        drafts=drafts,
        approvals=approvals,
        attempts=attempts,
    )


@router.get("/{lead_id}/outreach/{draft_id}", response_model=OutreachDraftResponse)
async def get_outreach_draft(
    lead_id: uuid.UUID,
    draft_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> OutreachDraftResponse:
    """Retrieves an individual outreach draft with associated evidence and audit records."""
    service = OutreachService(db)
    draft = await service.get_draft(organization_id=org_id, draft_id=draft_id)
    if not draft or draft.lead_id != lead_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outreach draft not found")
    return _to_draft_response(draft)


@router.post("/{lead_id}/outreach/{draft_id}/validate", response_model=ValidationDetailResponse)
async def validate_outreach_draft(
    lead_id: uuid.UUID,
    draft_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> ValidationDetailResponse:
    """Validates an outreach draft against evidence and recalculates its quality score."""
    service = OutreachService(db)
    draft, val_res = await service.validate_draft(organization_id=org_id, draft_id=draft_id)
    if not draft or draft.lead_id != lead_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outreach draft not found")

    return ValidationDetailResponse(
        valid=val_res.valid,
        score=val_res.score,
        errors=val_res.errors,
        warnings=val_res.warnings,
        unsupported_claims=val_res.unsupported_claims,
        evidence_coverage=val_res.evidence_coverage,
        personalization_score=val_res.personalization_score,
    )


@router.post("/{lead_id}/outreach/{draft_id}/approve", response_model=OutreachDraftResponse)
async def approve_outreach_draft(
    lead_id: uuid.UUID,
    draft_id: uuid.UUID,
    data: Optional[ApproveDraftRequest] = None,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> OutreachDraftResponse:
    """Approves an outreach draft via the human-in-the-loop safety gate (does not execute external send)."""
    service = OutreachService(db)
    reviewed_by = data.reviewed_by if data else "SAHIL"
    reason = data.decision_reason if data else "Approved outreach draft."

    try:
        draft = await service.approve_draft(
            organization_id=org_id,
            draft_id=draft_id,
            reviewed_by=reviewed_by,
            decision_reason=reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    if not draft or draft.lead_id != lead_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outreach draft not found")
    return _to_draft_response(draft)


@router.post("/{lead_id}/outreach/{draft_id}/reject", response_model=OutreachDraftResponse)
async def reject_outreach_draft(
    lead_id: uuid.UUID,
    draft_id: uuid.UUID,
    data: RejectDraftRequest,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> OutreachDraftResponse:
    """Rejects an outreach draft with an auditable reason."""
    service = OutreachService(db)
    try:
        draft = await service.reject_draft(
            organization_id=org_id,
            draft_id=draft_id,
            reviewed_by=data.reviewed_by,
            decision_reason=data.decision_reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    if not draft or draft.lead_id != lead_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outreach draft not found")
    return _to_draft_response(draft)


@router.post("/{lead_id}/outreach/{draft_id}/regenerate", response_model=OutreachDraftResponse)
async def regenerate_outreach_draft(
    lead_id: uuid.UUID,
    draft_id: uuid.UUID,
    data: Optional[RegenerateOutreachRequest] = None,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
) -> OutreachDraftResponse:
    """Regenerates a draft with updated preferences, marking previous draft as SUPERSEDED."""
    service = OutreachService(db)
    prefs = data.preferences if data else None
    target_channel = data.target_channel if data else None

    draft = await service.regenerate_draft(
        organization_id=org_id,
        draft_id=draft_id,
        preferences=prefs,
        target_channel=target_channel,
    )
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outreach draft not found for regeneration")
    return _to_draft_response(draft)
