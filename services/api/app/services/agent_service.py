import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared_types.agent import (
    ActionType,
    AgentState,
    ApprovalStatus,
    SessionStatus,
)
from packages.shared_types.crm import LeadType, NextAction, ScoreCategory, SignalType
from services.api.app.agents.browser.state_machine import BrowserAgentStateMachine
from services.api.app.agents.discovery.opportunity_detector import OpportunityDetector
from services.api.app.agents.personalization.draft_generator import DraftGenerator
from services.api.app.agents.signals.engine import SignalDetectionEngine
from services.api.app.models.agent import ActionApproval, AgentEvent, AgentSession
from services.api.app.models.crm import Lead, LeadSignal
from services.api.app.schemas.crm import LeadCreate, LeadSignalCreate
from services.api.app.services.crm_service import LeadService
from services.api.app.services.normalization import (
    normalize_domain,
    normalize_profile_url,
    normalize_username,
)


class AgentServiceException(Exception):
    """Base exception for agent operational errors."""
    pass


class ActionBlockedException(AgentServiceException):
    """Raised when an action is blocked by security boundaries or duplicate contact protection."""
    pass


class AgentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.lead_service = LeadService(session)

    # --- Session Management ---

    async def create_session(
        self,
        org_id: uuid.UUID,
        browser_id: str,
        user_id: Optional[uuid.UUID] = None,
        initial_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentSession:
        domain = normalize_domain(initial_url) if initial_url else None
        agent_session = AgentSession(
            organization_id=org_id,
            user_id=user_id,
            browser_id=browser_id,
            current_url=initial_url,
            current_domain=domain,
            status=SessionStatus.IDLE.value,
            metadata_json=metadata,
        )
        self.session.add(agent_session)
        await self.session.commit()
        await self.session.refresh(agent_session)
        return agent_session

    async def get_session(self, org_id: uuid.UUID, session_id: uuid.UUID) -> AgentSession:
        stmt = select(AgentSession).where(
            AgentSession.organization_id == org_id,
            AgentSession.id == session_id,
        )
        res = await self.session.execute(stmt)
        session = res.scalar_one_or_none()
        if not session:
            raise AgentServiceException(f"Agent session {session_id} not found in this organization")
        return session

    async def update_session_state(
        self,
        org_id: uuid.UUID,
        session_id: uuid.UUID,
        target_state: AgentState,
        reason: Optional[str] = None,
    ) -> AgentSession:
        agent_session = await self.get_session(org_id, session_id)
        current_agent_state = AgentState(agent_session.status)

        sm = BrowserAgentStateMachine(initial_state=current_agent_state)
        new_state = sm.transition_to(target_state)

        agent_session.status = new_state.value
        agent_session.last_activity_at = datetime.now(timezone.utc)

        # Log transition event
        event = AgentEvent(
            session_id=agent_session.id,
            event_type="state_transition",
            url=agent_session.current_url,
            input_summary=f"Transition from {current_agent_state.value} to {new_state.value}",
            output_summary=reason or "State updated successfully",
            status="SUCCESS",
        )
        self.session.add(event)

        await self.session.commit()
        await self.session.refresh(agent_session)
        return agent_session

    async def record_event(
        self,
        org_id: uuid.UUID,
        session_id: uuid.UUID,
        event_type: str,
        tool: Optional[str] = None,
        url: Optional[str] = None,
        input_summary: Optional[str] = None,
        output_summary: Optional[str] = None,
        status: str = "SUCCESS",
        duration_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentEvent:
        agent_session = await self.get_session(org_id, session_id)
        if url:
            agent_session.current_url = url
            agent_session.current_domain = normalize_domain(url)
        agent_session.last_activity_at = datetime.now(timezone.utc)

        event = AgentEvent(
            session_id=agent_session.id,
            event_type=event_type,
            tool=tool,
            url=url or agent_session.current_url,
            input_summary=input_summary,
            output_summary=output_summary,
            status=status,
            duration_ms=duration_ms,
            metadata_json=metadata,
        )
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event

    # --- Duplicate Contact Protection & Approvals ---

    async def check_contact_history(
        self,
        org_id: uuid.UUID,
        recipient: Optional[str] = None,
        target_url: Optional[str] = None,
        lead_id: Optional[uuid.UUID] = None,
    ) -> bool:
        """
        Check if recipient or lead has already been contacted.
        Returns True if previously contacted (executed outreach exists).
        """
        stmt = (
            select(ActionApproval)
            .join(AgentSession, ActionApproval.session_id == AgentSession.id)
            .where(
                AgentSession.organization_id == org_id,
                ActionApproval.status == ApprovalStatus.EXECUTED.value,
            )
        )

        conditions = []
        if recipient:
            norm_recip = normalize_username(recipient) or recipient.strip().lower()
            conditions.append(ActionApproval.recipient.ilike(f"%{norm_recip}%"))
        if lead_id:
            conditions.append(ActionApproval.lead_id == lead_id)

        if not conditions:
            return False

        from sqlalchemy import or_
        stmt = stmt.where(or_(*conditions)).limit(1)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none() is not None

    async def request_action_approval(
        self,
        org_id: uuid.UUID,
        session_id: uuid.UUID,
        action_type: ActionType,
        content: str,
        recipient: Optional[str] = None,
        target_url: Optional[str] = None,
        lead_id: Optional[uuid.UUID] = None,
        force_override: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ActionApproval:
        agent_session = await self.get_session(org_id, session_id)

        # Duplicate Contact Protection
        if not force_override:
            already_contacted = await self.check_contact_history(
                org_id=org_id,
                recipient=recipient,
                target_url=target_url,
                lead_id=lead_id,
            )
            if already_contacted:
                raise ActionBlockedException(
                    f"Outbound {action_type.value} blocked: Recipient '{recipient}' has already been contacted. "
                    "Duplicate outreach is prohibited without explicit override."
                )

        approval = ActionApproval(
            session_id=agent_session.id,
            lead_id=lead_id,
            action_type=action_type.value,
            target_url=target_url or agent_session.current_url,
            recipient=recipient,
            content=content,
            status=ApprovalStatus.PENDING.value,
            metadata_json=metadata,
        )
        self.session.add(approval)
        await self.session.commit()
        await self.session.refresh(approval)
        return approval

    async def review_action_approval(
        self,
        org_id: uuid.UUID,
        approval_id: uuid.UUID,
        decision: str,  # "APPROVED" or "REJECTED"
        reviewer: str = "Sahil",
    ) -> ActionApproval:
        stmt = (
            select(ActionApproval)
            .join(AgentSession, ActionApproval.session_id == AgentSession.id)
            .where(
                AgentSession.organization_id == org_id,
                ActionApproval.id == approval_id,
            )
        )
        res = await self.session.execute(stmt)
        approval = res.scalar_one_or_none()
        if not approval:
            raise AgentServiceException(f"Approval request {approval_id} not found")

        now = datetime.now(timezone.utc)
        if decision.upper() == "APPROVED":
            approval.status = ApprovalStatus.APPROVED.value
            approval.approved_at = now
            approval.approved_by = reviewer
        elif decision.upper() == "REJECTED":
            approval.status = ApprovalStatus.REJECTED.value
            approval.rejected_at = now
            approval.approved_by = reviewer
        else:
            raise AgentServiceException(f"Invalid approval decision: {decision}. Use 'APPROVED' or 'REJECTED'.")

        await self.session.commit()
        await self.session.refresh(approval)
        return approval

    async def execute_approved_action(
        self,
        org_id: uuid.UUID,
        approval_id: uuid.UUID,
    ) -> ActionApproval:
        stmt = (
            select(ActionApproval)
            .join(AgentSession, ActionApproval.session_id == AgentSession.id)
            .where(
                AgentSession.organization_id == org_id,
                ActionApproval.id == approval_id,
            )
        )
        res = await self.session.execute(stmt)
        approval = res.scalar_one_or_none()
        if not approval:
            raise AgentServiceException(f"Approval {approval_id} not found")

        if approval.status != ApprovalStatus.APPROVED.value:
            raise ActionBlockedException(
                f"Action execution refused: Approval status is '{approval.status}', but must be 'APPROVED'."
            )

        # Mark as EXECUTED
        approval.status = ApprovalStatus.EXECUTED.value

        event = AgentEvent(
            session_id=approval.session_id,
            event_type="action_executed",
            tool=f"send_{approval.action_type.lower()}",
            url=approval.target_url,
            input_summary=f"Recipient: {approval.recipient}, Action: {approval.action_type}",
            output_summary=f"Content sent: {approval.content[:100]}...",
            status="SUCCESS",
        )
        self.session.add(event)

        await self.session.commit()
        await self.session.refresh(approval)
        return approval

    # --- Page Observation & Opportunity Workflow ---

    async def observe_and_process_page(
        self,
        org_id: uuid.UUID,
        session_id: uuid.UUID,
        url: str,
        visible_text: str,
        recipient_handle: Optional[str] = None,
        profile_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Complete observe-evaluate-crm-draft workflow:
        1. Record page observation event
        2. Detect business opportunities from visible text
        3. If opportunity found: create CRM lead & signal, and generate personalized draft
        """
        agent_session = await self.get_session(org_id, session_id)
        agent_session.current_url = url
        agent_session.current_domain = normalize_domain(url)

        # 1. Observe event
        await self.record_event(
            org_id=org_id,
            session_id=session_id,
            event_type="content_observed",
            tool="read_page",
            url=url,
            input_summary=f"Observed visible content ({len(visible_text)} chars)",
            output_summary=visible_text[:200],
        )

        # 2. Opportunity & Signal Detection
        eval_result = OpportunityDetector.evaluate_content(text=visible_text)
        detected_signals = SignalDetectionEngine.analyze(text=visible_text, source_url=url)

        if not eval_result.is_opportunity and not detected_signals:
            return {
                "is_opportunity": False,
                "message": "No high-intent opportunity detected on current page",
            }
        elif not eval_result.is_opportunity and detected_signals:
            primary_sig = detected_signals[0]
            from services.api.app.agents.discovery.opportunity_detector import OpportunityEvaluation
            eval_result = OpportunityEvaluation(
                is_opportunity=True,
                opportunity_type=primary_sig.signal_type.value,
                confidence=primary_sig.confidence,
                evidence=[primary_sig.evidence],
                recommended_service="E-commerce Website" if primary_sig.signal_type == SignalType.ECOMMERCE_OPPORTUNITY else "Business Website",
                detected_intent=primary_sig.evidence,
            )

        # 3. CRM Lead Creation (if not already existing)
        clean_profile = normalize_profile_url(profile_url) or normalize_profile_url(url)
        lead = None
        try:
            lead = await self.lead_service.create_lead(
                LeadCreate(
                    organization_id=org_id,
                    title=f"Discovered via Browser: {recipient_handle or eval_result.recommended_service}",
                    summary=f"Detected {eval_result.opportunity_type}: {eval_result.detected_intent}",
                    lead_type=LeadType.COMPANY,
                    source_url=url,
                    profile_url=clean_profile,
                    intent_score=int(eval_result.confidence * 100),
                    overall_score=int(eval_result.confidence * 90),
                    recommended_service=eval_result.recommended_service,
                )
            )
            # Add initial signal from opportunity detector
            await self.lead_service.add_signal(
                org_id=org_id,
                data=LeadSignalCreate(
                    lead_id=lead.id,
                    signal_type=SignalType(eval_result.opportunity_type) if hasattr(SignalType, eval_result.opportunity_type or "") else SignalType.REQUEST_FOR_SERVICE,
                    confidence=eval_result.confidence,
                    evidence=eval_result.evidence[0] if eval_result.evidence else "Observed in browser session",
                    source_url=url,
                ),
            )
        except Exception:
            # If lead already exists or duplicate detected, fetch existing
            pass

        # 4. Phase 3 Signal Engine & Lead Qualification
        qualification = None
        if lead:
            try:
                _, qualification = await self.lead_service.analyze_signals(
                    org_id=org_id,
                    lead_id=lead.id,
                    text=visible_text,
                    source_url=url,
                )
            except Exception:
                pass

        # 5. Generate Personalized Outreach Draft
        handle = recipient_handle or "founder"
        rec_service = (
            qualification.recommended_service.value
            if (qualification and qualification.recommended_service)
            else (eval_result.recommended_service or "Business Website")
        )
        dm_draft = DraftGenerator.generate_dm_draft(
            recipient_handle=handle,
            opportunity_type=eval_result.opportunity_type or "WEBSITE_REQUEST",
            recommended_service=rec_service,
            observation=eval_result.evidence[0] if eval_result.evidence else None,
        )

        # 6. Create Action Approval Gate
        approval = await self.request_action_approval(
            org_id=org_id,
            session_id=session_id,
            action_type=dm_draft.action_type,
            content=dm_draft.content,
            recipient=dm_draft.recipient,
            target_url=url,
            lead_id=lead.id if lead else None,
            metadata={"reasoning": dm_draft.reasoning, "points": dm_draft.personalization_points},
        )

        return {
            "is_opportunity": True,
            "opportunity_type": eval_result.opportunity_type,
            "confidence": eval_result.confidence,
            "lead_id": str(lead.id) if lead else None,
            "approval_id": str(approval.id) if approval else None,
            "draft_content": dm_draft.content if dm_draft else None,
            "approval_status": approval.status if approval else None,
            "overall_score": qualification.overall_score if qualification else int(eval_result.confidence * 90),
            "category": qualification.category.value if qualification else "GOOD",
            "score_breakdown": qualification.score_breakdown.model_dump() if qualification else {},
            "recommended_service": rec_service,
            "recommended_next_action": qualification.recommended_next_action.value if qualification else "PREPARE_OUTREACH",
        }
