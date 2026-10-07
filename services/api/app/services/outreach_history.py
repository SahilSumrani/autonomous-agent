import uuid
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared_types.crm import LeadStatus
from packages.shared_types.outreach import DraftStatus, OutreachChannel
from services.api.app.repositories.outreach import OutreachRepository


class OutreachHistoryManager:
    """Manages duplicate outreach protection, attempt tracking, and history auditing."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = OutreachRepository(session)

    async def check_duplicate_protection(
        self,
        organization_id: uuid.UUID,
        lead_id: uuid.UUID,
        channel: OutreachChannel,
        recipient: Optional[str] = None,
        override_duplicate: bool = False,
    ) -> Tuple[bool, Optional[str]]:
        """Returns (is_allowed, block_reason). If blocked, is_allowed is False."""
        if override_duplicate:
            return True, None

        # 1. Check existing drafts for this lead on this channel
        drafts = await self.repo.list_drafts_by_lead(organization_id, lead_id)
        for d in drafts:
            if d.channel == channel.value:
                # If already approved or sent
                if d.status in [DraftStatus.APPROVED.value, DraftStatus.SENT.value]:
                    return False, f"Outreach already {d.status} for this lead on channel {channel.value}."
                # If existing pending approval
                if d.status == DraftStatus.READY_FOR_APPROVAL.value:
                    return False, f"A draft is already pending review/approval on {channel.value}."

        # 2. Check previous attempts
        attempts = await self.repo.list_attempts_by_lead(organization_id, lead_id)
        for att in attempts:
            if recipient and att.recipient and att.recipient.lower() == recipient.lower() and att.status == "CONTACTED":
                return False, f"Recipient {recipient} was already contacted previously."

        return True, None
