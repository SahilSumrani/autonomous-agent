from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from packages.shared_types.conversation import ProspectIntent, SalesStage


class MessageSummaryItem(BaseModel):
    direction: str
    author_type: str
    content: str
    created_at: Optional[str] = None


class ConversationContext(BaseModel):
    lead_id: str
    organization_id: str
    lead_title: Optional[str] = None
    company_name: Optional[str] = None
    contact_handle: Optional[str] = None
    recommended_service: Optional[str] = None
    lead_score: int = 0
    signals_summary: List[str] = Field(default_factory=list)
    website_findings: List[str] = Field(default_factory=list)
    previous_outreach_body: Optional[str] = None
    previous_outreach_channel: Optional[str] = None
    recent_messages: List[MessageSummaryItem] = Field(default_factory=list)
    current_summary: Optional[str] = None
    sales_stage: str = SalesStage.CONTACTED.value
    latest_intent: Optional[str] = None


class ConversationMemoryManager:
    """
    Maintains persistent conversational context and generates rolling summaries.
    Avoids sending excessive tokens while keeping vital sales intelligence grounded.
    """

    @classmethod
    def generate_rolling_summary(
        cls,
        existing_summary: Optional[str],
        new_messages: List[MessageSummaryItem],
    ) -> str:
        """
        Synthesizes a factual, evidence-based rolling summary from exchanged messages.
        """
        if not new_messages and existing_summary:
            return existing_summary

        lines: List[str] = []
        if existing_summary:
            lines.append(f"Prior Context: {existing_summary.strip()}")

        for msg in new_messages:
            author = "Prospect" if msg.direction == "INBOUND" else "TechVerse"
            lines.append(f"- {author}: {msg.content.strip()[:180]}")

        # Compact summary into max 600 characters
        summary_text = " | ".join(lines)
        if len(summary_text) > 600:
            summary_text = summary_text[-600:]
        return summary_text
