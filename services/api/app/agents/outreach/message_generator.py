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
    async def generate_variants_async(
        cls,
        context: OutreachContext,
        channel: OutreachChannel,
        variant_count: int = 3,
        preferences: Optional[List[str]] = None,
        ai_provider: Optional[Any] = None,
    ) -> List[OutreachDraftResult]:
        deterministic_drafts = cls.generate_variants(
            context=context,
            channel=channel,
            variant_count=variant_count,
            preferences=preferences,
        )
        if not ai_provider:
            return deterministic_drafts

        refined_results: List[OutreachDraftResult] = []
        for d in deterministic_drafts:
            try:
                system_prompt = (
                    "You are a technical B2B outreach copywriter for TechVerse AI. "
                    "Refine the clarity and tone of this message while strictly adhering to ONLY the observed facts. "
                    "NEVER add any new factual claims, performance metrics, store launches, or unverified findings."
                )
                prompt = f"Refine the following draft while preserving all exact factual constraints:\n\n{d.body}"
                refined_text = await ai_provider.generate_text(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_tokens=300,
                    temperature=0.3,
                )
                if refined_text and len(refined_text.strip()) > 20:
                    val_res = MessageValidator.validate_draft(
                        body=refined_text.strip(),
                        context=context,
                        channel=channel,
                    )
                    if val_res.valid:
                        refined_draft = OutreachDraftResult(
                            variant=d.variant,
                            channel=d.channel,
                            subject=d.subject,
                            body=refined_text.strip(),
                            personalization_level=d.personalization_level,
                            angle=d.angle,
                            service=d.service,
                            cta_text=d.cta_text,
                            cta_category=d.cta_category,
                            quality_score=val_res.score,
                            validation_result=val_res,
                            evidence_items=d.evidence_items,
                            status=DraftStatus.READY_FOR_APPROVAL,
                        )
                        refined_results.append(refined_draft)
                        continue
            except Exception:
                pass  # Fall back cleanly to deterministic draft
            refined_results.append(d)

        return refined_results

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
        has_inspected_site = bool(context.website_url and (context.website_audit or context.verified_observations))
        obs_ref = ""
        if context.verified_observations:
            obs_ref = f"noticed your recent update on {context.verified_observations[0]}"
        elif has_inspected_site:
            obs_ref = f"noticed {company_name}'s web presence"
        else:
            obs_ref = f"noticed your work on {company_name}"

        pain_sentence = ""
        if primary_pain:
            if has_inspected_site:
                pain_sentence = f" I also noticed {primary_pain.lower().rstrip('.')} on the site."
            else:
                pain_sentence = f" I also noted your point regarding {primary_pain.lower().rstrip('.')}."

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
                f"If you're actively refining the experience, happy to share a few specific ideas."
            )
        else:
            # Insight-led
            followup_offer = "the key technical observations I noted if helpful." if (primary_pain and has_inspected_site) else "our technical playbook if helpful."
            return (
                f"{contact_ref}, was looking over {company_name}'s public presence.{pain_sentence} "
                f"We focus on {val_prop.lower()} "
                f"Happy to send over {followup_offer}"
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
        pain_mention = primary_pain.lower() if primary_pain else "asset optimization and layout structure"
        return (
            f"A few key areas I'd check first are {pain_mention}. "
            f"Often streamlining asset sizes and clarifying product CTAs makes a measurable difference. "
            f"If you'd like, I can take a closer look and share specific ideas."
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
        has_inspected_site = bool(context.website_url and (context.website_audit or context.verified_observations))
        intro = (
            f"I was recently checking out {company_name} and took a close look at your public web experience."
            if has_inspected_site
            else f"I was recently reviewing {company_name}'s public digital presence."
        )

        if primary_pain and has_inspected_site:
            pain_section = f"While reviewing the site, I noticed {primary_pain.lower().rstrip('.')}."
        elif primary_pain:
            pain_section = f"Based on your public requirements, addressing {primary_pain.lower().rstrip('.')} is often a critical priority."
        else:
            pain_section = "At TechVerse AI, we engineer high-performance web systems and digital experiences."

        return (
            f"{contact_ref}\n\n"
            f"{intro}\n\n"
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
        has_inspected_site = bool(context.website_url and (context.website_audit or context.verified_observations))
        pain_mention = ""
        if primary_pain:
            if has_inspected_site:
                pain_mention = f" I noticed {primary_pain.lower().rstrip('.')} on the mobile site."
            else:
                pain_mention = f" I noticed your focus on {primary_pain.lower().rstrip('.')}."

        return (
            f"{contact_ref}, came across {company_name}'s digital presence.{pain_mention} "
            f"We build high-performance web experiences at TechVerse AI to {val_prop.lower()} "
            f"Would it be helpful to see a quick teardown of how we'd approach this?"
        )
