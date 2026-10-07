from packages.shared_types.outreach import CtaCategory, OutreachChannel


class CtaGenerator:
    """Generates natural, proportionate CTAs based on channel, intent, and friction level."""

    @classmethod
    def generate_cta(
        cls,
        channel: OutreachChannel,
        category: CtaCategory = CtaCategory.SOFT_QUESTION,
        company_name: str = "your store",
    ) -> str:
        if channel == OutreachChannel.REDDIT_REPLY:
            if category == CtaCategory.OFFER_AUDIT:
                return "If you'd like, I can take a deeper look at the public storefront and point out the specific friction points."
            return "Happy to share more technical context on how we resolved similar bottlenecks if helpful."

        if channel == OutreachChannel.INSTAGRAM_DM:
            if category == CtaCategory.OFFER_INSIGHT:
                return "If you're currently refining the storefront, happy to share a few specific ideas."
            if category == CtaCategory.OFFER_AUDIT:
                return "Happy to send over the 3 biggest friction points I noticed on mobile if helpful."
            if category == CtaCategory.ASK_PERMISSION:
                return "Mind if I share a quick note on the mobile navigation points I spotted?"
            if category == CtaCategory.MEETING:
                return "If you're actively working on this, happy to chat for 10 minutes."
            return "Would it be useful if I shared a couple of observations on the user flow?"

        if channel == OutreachChannel.EMAIL:
            if category == CtaCategory.MEETING:
                return "If this aligns with your current roadmap, would you be open to a 10-minute call later this week?"
            if category == CtaCategory.OFFER_AUDIT:
                return "I put together 3 actionable recommendations for the mobile experience—would you like me to send them over?"
            return "Would it make sense to share a quick technical breakdown with your team?"

        # Default fallback
        return "Would it be helpful to see a quick teardown of how we'd address this?"
