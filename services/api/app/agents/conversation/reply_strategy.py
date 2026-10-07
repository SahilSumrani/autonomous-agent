from typing import List, Optional
from pydantic import BaseModel, Field

from packages.shared_types.conversation import (
    ObjectionClassification,
    ProspectIntent,
    ReplyObjective,
)
from services.api.app.agents.conversation.conversation_memory import ConversationContext


class ReplyStrategy(BaseModel):
    objective: ReplyObjective
    recommended_tone: str
    recommended_cta: str
    information_to_include: List[str] = Field(default_factory=list)
    information_to_avoid: List[str] = Field(default_factory=list)
    requires_human_approval: bool = True
    reasoning: str


class ReplyStrategyEngine:
    """
    Determines strategic reply posture and CTA based on classified intent and context.
    """

    @classmethod
    def determine(
        cls,
        intent: ProspectIntent,
        objection: Optional[ObjectionClassification],
        context: ConversationContext,
    ) -> ReplyStrategy:
        service_name = context.recommended_service or "Custom Web Development"

        # 1. Objections take precedence
        if objection:
            return ReplyStrategy(
                objective=ReplyObjective.HANDLE_OBJECTION,
                recommended_tone="Consultative, transparent, respectful",
                recommended_cta="Offer an open-ended review of modular options or invite questions.",
                information_to_include=[
                    objection.recommended_strategy,
                    f"Specialization in {service_name}",
                    "Milestone deliverables and scope flexibility",
                ],
                information_to_avoid=objection.do_not_claim,
                requires_human_approval=True,
                reasoning=f"Active objection ({objection.objection_type}) detected; requires careful consultative framing.",
            )

        # 2. Rejection / Opt-out
        if intent == ProspectIntent.NOT_INTERESTED:
            return ReplyStrategy(
                objective=ReplyObjective.DO_NOT_REPLY,
                recommended_tone="Polite, respectful, final",
                recommended_cta="None",
                information_to_include=["Brief acknowledgment thanking them for their time."],
                information_to_avoid=["Pitching", "Follow-up requests", "Arguments"],
                requires_human_approval=True,
                reasoning="Prospect expressed disinterest; respect opt-out immediately.",
            )

        # 3. Meeting Request
        if intent == ProspectIntent.MEETING_REQUEST:
            return ReplyStrategy(
                objective=ReplyObjective.REQUEST_MEETING,
                recommended_tone="Direct, enthusiastic, organized",
                recommended_cta="Provide simple scheduling options or ask for their preferred time window.",
                information_to_include=[
                    "Available meeting times or simple calendar link",
                    f"Brief preview of agenda discussing their {service_name} goals",
                ],
                information_to_avoid=["Lengthy pitches", "Unnecessary delays"],
                requires_human_approval=True,
                reasoning="Prospect requested a meeting; confirm coordination directly.",
            )

        # 4. High Interest
        if intent == ProspectIntent.HIGH_INTEREST:
            return ReplyStrategy(
                objective=ReplyObjective.REQUEST_MEETING,
                recommended_tone="Decisive, professional, actionable",
                recommended_cta="Suggest a 15-minute introductory technical alignment call.",
                information_to_include=[
                    "Clear next steps",
                    f"Readiness to kick off discovery for {service_name}",
                ],
                information_to_avoid=["Overwhelming attachments", "Premature legal terms"],
                requires_human_approval=True,
                reasoning="Prospect shows strong buying intent; propose quick technical alignment call.",
            )

        # 5. Pricing Request
        if intent == ProspectIntent.PRICING_REQUEST:
            return ReplyStrategy(
                objective=ReplyObjective.QUALIFY,
                recommended_tone="Transparent, consultative, realistic",
                recommended_cta="Ask 1-2 scoping questions or suggest a quick walkthrough to provide an accurate estimate.",
                information_to_include=[
                    "Acknowledgment of pricing request",
                    "Explanation that cost depends on scope, architecture, and specific requirements",
                    "Invitation to review high-level requirements together",
                ],
                information_to_avoid=[
                    "Inventing an unauthorized fixed dollar quote without human review",
                    "Offering arbitrary discounts",
                ],
                requires_human_approval=True,
                reasoning="Pricing requests must explain scoping dependencies and be reviewed by a human before quoting numbers.",
            )

        # 6. Portfolio Request
        if intent == ProspectIntent.PORTFOLIO_REQUEST:
            return ReplyStrategy(
                objective=ReplyObjective.SHARE_PORTFOLIO,
                recommended_tone="Confident, evidence-driven, concise",
                recommended_cta="Ask if they would like to see relevant live examples matching their niche.",
                information_to_include=[
                    f"Overview of TechVerse's recent builds in {service_name}",
                    "Verified technical deliverables and design systems",
                ],
                information_to_avoid=[
                    "Fabricated client names or revenue stats",
                    "Sending broken or unverified URLs",
                ],
                requires_human_approval=True,
                reasoning="Prospect requested proof of work; provide relevant verified capability samples.",
            )

        # 7. Service Details
        if intent == ProspectIntent.SERVICE_DETAILS:
            return ReplyStrategy(
                objective=ReplyObjective.ANSWER,
                recommended_tone="Informative, technical, clear",
                recommended_cta="Ask what their primary architectural or feature priority is.",
                information_to_include=[
                    f"Core capabilities regarding {service_name}",
                    "Modern tech stack details (clean responsive frontend, robust backends, fast checkout)",
                ],
                information_to_avoid=["Jargon dumps", "Over-promising custom features"],
                requires_human_approval=True,
                reasoning="Prospect asked about service capabilities; provide structured technical clarity.",
            )

        # 8. Follow-up Later
        if intent == ProspectIntent.FOLLOW_UP_LATER:
            return ReplyStrategy(
                objective=ReplyObjective.FOLLOW_UP,
                recommended_tone="Understanding, patient, professional",
                recommended_cta="Confirm their preferred month/quarter to check back in.",
                information_to_include=[
                    "Full respect for their timeline",
                    "Agreement to reconnect when timing is optimal",
                ],
                information_to_avoid=["Aggressive follow-ups", "FOMO pressure"],
                requires_human_approval=True,
                reasoning="Prospect requested a delayed touchpoint; log and respect the timing boundary.",
            )

        # 9. Incumbent Vendor
        if intent == ProspectIntent.EXISTING_VENDOR:
            return ReplyStrategy(
                objective=ReplyObjective.CLARIFY,
                recommended_tone="Respectful, low-pressure, supportive",
                recommended_cta="Offer to remain a resource if they ever need overflow capacity or third-party audits.",
                information_to_include=[
                    "Appreciation for their existing team setup",
                    "Willingness to assist solely as a backup or specialized consultant if needed",
                ],
                information_to_avoid=["Criticizing their vendor", "Pushy sales arguments"],
                requires_human_approval=True,
                reasoning="Prospect already has a vendor; maintain high-reputation low-friction relationship.",
            )

        # 10. Default General Question / Interest
        return ReplyStrategy(
            objective=ReplyObjective.ANSWER,
            recommended_tone="Helpful, conversational, focused",
            recommended_cta="Ask a relevant follow-up question to advance the discussion.",
            information_to_include=[
                "Direct answer to the prospect's query",
                f"Contextual alignment with {service_name}",
            ],
            information_to_avoid=["Spam copy", "Generic sales filler"],
            requires_human_approval=True,
            reasoning="Provide a clear, grounded conversational answer.",
        )
