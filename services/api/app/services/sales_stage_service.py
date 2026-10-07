from typing import Optional
from packages.shared_types.conversation import ProspectIntent, SalesStage


class SalesStageService:
    """
    Deterministic state machine for conversation-aware sales stages.
    Enforces valid progression: CONTACTED -> REPLIED -> QUALIFIED_CONVERSATION -> INTERESTED -> MEETING_REQUESTED.
    Does NOT automatically mark deals as WON or closed without human intervention.
    """

    ALLOWED_TRANSITIONS = {
        SalesStage.CONTACTED: [
            SalesStage.REPLIED,
            SalesStage.QUALIFIED_CONVERSATION,
            SalesStage.INTERESTED,
            SalesStage.MEETING_REQUESTED,
            SalesStage.LOST,
            SalesStage.HUMAN_REVIEW,
        ],
        SalesStage.REPLIED: [
            SalesStage.QUALIFIED_CONVERSATION,
            SalesStage.INTERESTED,
            SalesStage.MEETING_REQUESTED,
            SalesStage.LOST,
            SalesStage.HUMAN_REVIEW,
        ],
        SalesStage.QUALIFIED_CONVERSATION: [
            SalesStage.INTERESTED,
            SalesStage.MEETING_REQUESTED,
            SalesStage.LOST,
            SalesStage.HUMAN_REVIEW,
        ],
        SalesStage.INTERESTED: [
            SalesStage.MEETING_REQUESTED,
            SalesStage.MEETING_SCHEDULED,
            SalesStage.PROPOSAL_READY,
            SalesStage.LOST,
            SalesStage.HUMAN_REVIEW,
        ],
        SalesStage.MEETING_REQUESTED: [
            SalesStage.MEETING_SCHEDULED,
            SalesStage.LOST,
            SalesStage.HUMAN_REVIEW,
        ],
        SalesStage.MEETING_SCHEDULED: [
            SalesStage.PROPOSAL_READY,
            SalesStage.LOST,
            SalesStage.HUMAN_REVIEW,
        ],
        SalesStage.PROPOSAL_READY: [
            SalesStage.WON,
            SalesStage.LOST,
            SalesStage.HUMAN_REVIEW,
        ],
        SalesStage.WON: [],  # Terminal
        SalesStage.LOST: [SalesStage.CONTACTED],  # Re-engagement
        SalesStage.HUMAN_REVIEW: [
            SalesStage.REPLIED,
            SalesStage.QUALIFIED_CONVERSATION,
            SalesStage.INTERESTED,
            SalesStage.MEETING_REQUESTED,
            SalesStage.WON,
            SalesStage.LOST,
        ],
    }

    @classmethod
    def evaluate_next_stage(
        cls,
        current_stage_str: str,
        intent: ProspectIntent,
    ) -> str:
        try:
            current_stage = SalesStage(current_stage_str)
        except ValueError:
            current_stage = SalesStage.CONTACTED

        target_stage: Optional[SalesStage] = None

        if intent in (ProspectIntent.NOT_INTERESTED, ProspectIntent.SPAM_OR_BOT):
            target_stage = SalesStage.LOST
        elif intent == ProspectIntent.MEETING_REQUEST:
            target_stage = SalesStage.MEETING_REQUESTED
        elif intent == ProspectIntent.HIGH_INTEREST:
            target_stage = SalesStage.INTERESTED
        elif intent in (ProspectIntent.INTERESTED, ProspectIntent.PRICING_REQUEST, ProspectIntent.PORTFOLIO_REQUEST):
            target_stage = SalesStage.QUALIFIED_CONVERSATION
        elif current_stage == SalesStage.CONTACTED:
            target_stage = SalesStage.REPLIED

        if target_stage and cls.is_valid_transition(current_stage, target_stage):
            return target_stage.value

        return current_stage.value

    @classmethod
    def is_valid_transition(cls, from_stage: SalesStage, to_stage: SalesStage) -> bool:
        if from_stage == to_stage:
            return True
        allowed = cls.ALLOWED_TRANSITIONS.get(from_stage, [])
        return to_stage in allowed
