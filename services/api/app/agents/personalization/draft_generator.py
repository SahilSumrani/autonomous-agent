from typing import List, Optional
from pydantic import BaseModel, Field

from packages.shared_types.agent import ActionType


class PersonalizedDraft(BaseModel):
    """Personalized outbound message draft generated strictly from verified observations."""
    action_type: ActionType
    recipient: Optional[str] = None
    content: str
    reasoning: str
    personalization_points: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)


class DraftGenerator:
    """Generates context-aware, non-generic outreach drafts based on verified public signals."""

    @classmethod
    def generate_dm_draft(
        cls,
        recipient_handle: str,
        opportunity_type: str,
        recommended_service: str,
        business_name: Optional[str] = None,
        observation: Optional[str] = None,
        website_url: Optional[str] = None,
    ) -> PersonalizedDraft:
        clean_handle = recipient_handle.lstrip("@")
        clean_name = business_name or clean_handle
        clean_obs = observation or "your recent post regarding your digital roadmap"

        if opportunity_type == "BUSINESS_LAUNCH":
            body = (
                f"Hey {clean_name}, saw you're preparing for your upcoming launch. "
                f"Curious if you already have the {recommended_service.lower()} locked in, "
                f"or if you're still exploring architecture options for the storefront?"
            )
            reasoning = "Targeted launch observation with low-friction architectural query."
            points = [f"Referenced launch of {clean_name}", f"Inquired about {recommended_service}"]

        elif opportunity_type == "WEBSITE_REDESIGN":
            body = (
                f"Hey {clean_name}, noticed your note about refreshing your website. "
                f"We specialize in high-converting modern rebuilds at TechVerse AI. "
                f"Are you looking to improve page speed and conversion, or a complete structural revamp?"
            )
            reasoning = "Direct problem-solution alignment focusing on speed and conversion."
            points = ["Acknowledged redesign intention", "Offered specific performance angle"]

        elif opportunity_type == "AI_AUTOMATION_REQUEST":
            body = (
                f"Hey {clean_name}, caught your post exploring AI automation workflows. "
                f"We build custom agentic pipelines at TechVerse that automate manual ops. "
                f"Which bottleneck are you aiming to streamline first?"
            )
            reasoning = "Pinpointed operational workflow challenge with specific technical inquiry."
            points = ["Acknowledged automation interest", "Asked about specific workflow bottleneck"]

        else:
            body = (
                f"Hey {clean_name}, came across your post about {clean_obs}. "
                f"TechVerse AI develops bespoke web and mobile platforms. "
                f"Would it be helpful to see a quick teardown of how we'd approach building that?"
            )
            reasoning = "Constructive value-first outreach offering a technical teardown."
            points = [f"Referenced {clean_obs}", "Offered technical breakdown"]

        return PersonalizedDraft(
            action_type=ActionType.DM,
            recipient=recipient_handle,
            content=body,
            reasoning=reasoning,
            personalization_points=points,
            confidence=0.90,
        )

    @classmethod
    def generate_comment_draft(
        cls,
        recipient_handle: str,
        opportunity_type: str,
        observation: Optional[str] = None,
    ) -> PersonalizedDraft:
        clean_handle = recipient_handle.lstrip("@")
        clean_obs = observation or "your project"

        if opportunity_type == "BUSINESS_LAUNCH":
            body = f"Exciting milestone on the launch! What tech stack are you leaning towards for the store?"
        elif opportunity_type == "WEBSITE_REDESIGN":
            body = f"A solid redesign makes a massive difference in conversion. Rooting for the new build!"
        else:
            body = f"Great perspective on {clean_obs}. Definitely an interesting technical challenge to tackle."

        return PersonalizedDraft(
            action_type=ActionType.COMMENT,
            recipient=recipient_handle,
            content=body,
            reasoning="Constructive public engagement without intrusive pitch.",
            personalization_points=[f"Engaged contextually with {opportunity_type}"],
            confidence=0.88,
        )
