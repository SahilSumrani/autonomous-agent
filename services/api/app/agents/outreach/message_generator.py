from typing import List, Optional
from packages.shared_types.outreach import (
    CtaCategory,
    DraftStatus,
    OutreachAngle,
    OutreachChannel,
    PersonalizationLevel,
)
from services.api.app.agents.outreach.channel_strategy import ChannelLimits
from services.api.app.agents.outreach.cta_generator import CtaGenerator
from services.api.app.agents.outreach.message_validator import MessageValidator
from services.api.app.agents.outreach.outreach_models import (
    OutreachContext,
    OutreachDraftResult,
)
from services.api.app.agents.outreach.personalization_engine import PersonalizationEngine


class MessageGenerator:
    """Generates structured, natural, evidence-driven outreach drafts across channels."""

    @classmethod
    def generate_variants(
        cls,
        context: OutreachContext,
        channel: OutreachChannel,
        variant_count: int = 3,
        preferences: Optional[List[str]] = None,
    ) -> List[OutreachDraftResult]:
        variants = ["A", "B", "C"][:variant_count]
        results: List[OutreachDraftResult] = []

        pers_level = PersonalizationEngine.evaluate_personalization_level(context)
        val_prop = PersonalizationEngine.select_value_proposition(
            service=context.recommended_service,
            angle=context.recommended_angle,
            pain_points=context.pain_points,
        )

        for v in variants:
            draft_res = cls._generate_single_variant(
                variant=v,
                context=context,
                channel=channel,
                pers_level=pers_level,
                value_proposition=val_prop,
                preferences=preferences or [],
            )
            results.append(draft_res)

        return results

    @classmethod
    def _generate_single_variant(
        cls,
        variant: str,
        context: OutreachContext,
        channel: OutreachChannel,
        pers_level: PersonalizationLevel,
        value_proposition: str,
        preferences: List[str],
    ) -> OutreachDraftResult:
        company_name = context.company_name or "your company"
        contact_ref = f"Hey {context.contact_name}" if context.contact_name else f"Hey {company_name}"
        if channel == OutreachChannel.EMAIL:
            contact_ref = f"Hi {context.contact_name}," if context.contact_name else f"Hi {company_name} team,"

        # Extract primary pain point observation if present
        primary_pain = None
        if context.pain_points:
            primary_pain = context.pain_points[0].statement

        # Check preferences
        is_shorter = "shorter" in preferences
        is_direct = "more direct" in preferences or variant == "A"
        is_conversational = "more conversational" in preferences or variant == "B"
        is_insight_led = "insight-led" in preferences or variant == "C"

        subject = None
        if channel == OutreachChannel.EMAIL:
            if context.website_url:
                subject = f"A few observations about {company_name}'s web experience"
            else:
                subject = f"Quick note regarding {company_name}'s digital roadmap"

        # Generate body based on channel and variant angle
        if channel == OutreachChannel.INSTAGRAM_DM:
            body = cls._build_instagram_dm(
                variant=variant,
                contact_ref=contact_ref,
                company_name=company_name,
                context=context,
                primary_pain=primary_pain,
                val_prop=value_proposition,
                is_shorter=is_shorter,
            )
            cta_cat = CtaCategory.SOFT_QUESTION if variant == "B" else CtaCategory.OFFER_INSIGHT
            cta_text = CtaGenerator.generate_cta(channel, cta_cat, company_name)

        elif channel == OutreachChannel.REDDIT_REPLY:
            body = cls._build_reddit_reply(
                variant=variant,
                context=context,
                primary_pain=primary_pain,
                val_prop=value_proposition,
                is_shorter=is_shorter,
            )
            cta_cat = CtaCategory.OFFER_INSIGHT
            cta_text = CtaGenerator.generate_cta(channel, cta_cat, company_name)

        elif channel == OutreachChannel.EMAIL:
            body = cls._build_email(
                variant=variant,
                contact_ref=contact_ref,
                company_name=company_name,
                context=context,
                primary_pain=primary_pain,
                val_prop=value_proposition,
                is_shorter=is_shorter,
            )
            cta_cat = CtaCategory.MEETING if variant == "A" else CtaCategory.OFFER_AUDIT
            cta_text = CtaGenerator.generate_cta(channel, cta_cat, company_name)

        else:  # LINKEDIN_MESSAGE
            body = cls._build_linkedin_message(
                variant=variant,
                contact_ref=contact_ref,
                company_name=company_name,
                context=context,
                primary_pain=primary_pain,
                val_prop=value_proposition,
                is_shorter=is_shorter,
            )
            cta_cat = CtaCategory.SOFT_QUESTION
            cta_text = CtaGenerator.generate_cta(channel, cta_cat, company_name)

        # Validate draft
        val_res = MessageValidator.validate_draft(
            body=body,
            context=context,
            channel=channel,
        )

        status = DraftStatus.READY_FOR_APPROVAL if val_res.valid else DraftStatus.NEEDS_REVIEW

        return OutreachDraftResult(
            variant=variant,
            channel=channel,
            subject=subject,
            body=body,
            personalization_level=pers_level,
            angle=context.recommended_angle,
            service=context.recommended_service,
            cta_text=cta_text,
            cta_category=cta_cat,
            quality_score=val_res.score,
            validation_result=val_res,
            evidence_items=context.evidence,
            status=status,
        )

    @classmethod
    def _build_instagram_dm(
        cls,
        variant: str,
        contact_ref: str,
        company_name: str,
        context: OutreachContext,
        primary_pain: Optional[str],
        val_prop: str,
        is_shorter: bool,
    ) -> str:
        obs_ref = ""
        if context.verified_observations:
            obs_ref = f"noticed your recent update on {context.verified_observations[0]}"
        elif context.website_url:
            obs_ref = f"saw you recently launched the {company_name} online store"
        else:
            obs_ref = f"noticed your work on {company_name}"

        pain_sentence = ""
        if primary_pain:
            pain_sentence = f" I also noticed {primary_pain.lower().rstrip('.')} on the mobile site."
        elif "ECOMMERCE" in context.recommended_service:
            pain_sentence = " I also noticed a couple areas in the mobile shopping flow that could be smoother."

        if is_shorter or variant == "A":
            # Direct
            return (
                f"{contact_ref}, {obs_ref}.{pain_sentence} "
                f"We help brands with {context.recommended_service.lower().replace('_', ' ')} at TechVerse AI. "
                f"Would it be helpful if I shared a couple of observations on the user flow?"
            )
        elif variant == "B":
            # Conversational
            return (
                f"{contact_ref}, {obs_ref}. "
                f"Really like what you're putting together for {company_name}.{pain_sentence} "
                f"If you're actively refining the storefront, happy to share a few specific ideas."
            )
        else:
            # Insight-led
            return (
                f"{contact_ref}, was looking over {company_name}'s public web storefront.{pain_sentence} "
                f"We focus on {val_prop.lower()} "
                f"Happy to send over the 3 biggest friction points I noticed on mobile if helpful."
            )

    @classmethod
    def _build_reddit_reply(
        cls,
        variant: str,
        context: OutreachContext,
        primary_pain: Optional[str],
        val_prop: str,
        is_shorter: bool,
    ) -> str:
        pain_mention = primary_pain or "mobile navigation friction and checkout drop-off"
        return (
            f"A few key areas I'd check first are {pain_mention.lower()}. "
            f"Often streamlining asset sizes and clarifying product CTAs makes a measurable difference. "
            f"If you'd like, I can take a deeper look at the public storefront and point out the specific friction points."
        )

    @classmethod
    def _build_email(
        cls,
        variant: str,
        contact_ref: str,
        company_name: str,
        context: OutreachContext,
        primary_pain: Optional[str],
        val_prop: str,
        is_shorter: bool,
    ) -> str:
        pain_section = f"While reviewing the site, I noticed {primary_pain.lower().rstrip('.')}." if primary_pain else f"While checking out {company_name}, I spotted a few potential friction points in the user journey."
        return (
            f"{contact_ref}\n\n"
            f"I was recently checking out {company_name} and took a close look at your public web experience.\n\n"
            f"{pain_section} At TechVerse AI, we specialize in high-impact {context.recommended_service.lower().replace('_', ' ')} to {val_prop.lower()}\n\n"
            f"Would it make sense to share a quick technical breakdown with your team?\n\n"
            f"Best regards,\n"
            f"TechVerse AI Team"
        )

    @classmethod
    def _build_linkedin_message(
        cls,
        variant: str,
        contact_ref: str,
        company_name: str,
        context: OutreachContext,
        primary_pain: Optional[str],
        val_prop: str,
        is_shorter: bool,
    ) -> str:
        pain_mention = f" I noticed {primary_pain.lower().rstrip('.')} on the mobile site." if primary_pain else ""
        return (
            f"{contact_ref}, came across {company_name}'s digital presence.{pain_mention} "
            f"We build high-performance web experiences at TechVerse AI to {val_prop.lower()} "
            f"Would it be helpful to see a quick teardown of how we'd approach this?"
        )
