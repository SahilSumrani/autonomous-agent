from packages.shared_types.crm import TechVerseService
from services.api.app.models.crm import Company, Contact, Lead, LeadSignal, LeadSource
from packages.shared_types.outreach import (
    CtaCategory,
    OutreachAngle,
    OutreachChannel,
    PainPointCategory,
    PersonalizationLevel,
)
from services.api.app.agents.outreach.outreach_models import (
    OutreachContext,
    OutreachEvidenceModel,
    PainPoint,
)
from services.api.app.models.research import WebsiteResearch


class OutreachContextBuilder:
    """Builds unified, evidence-rich outreach context combining CRM, Phase 3, and Phase 4."""

    @classmethod
    def build_context(
        cls,
        lead: Lead,
        company: Optional[Company] = None,
        contact: Optional[Contact] = None,
        sources: Optional[List[LeadSource]] = None,
        signals: Optional[List[LeadSignal]] = None,
        website_research: Optional[WebsiteResearch] = None,
        previous_outreach: Optional[List[Dict[str, Any]]] = None,
        previous_replies: Optional[List[Dict[str, Any]]] = None,
    ) -> OutreachContext:
        verified_observations: List[str] = []
        verified_signals: List[str] = []
        evidence_list: List[OutreachEvidenceModel] = []
        pain_points: List[PainPoint] = []
        opportunity_points: List[str] = []

        meta = getattr(lead, "metadata_json", None) or {}

        # 1. Company and CRM context
        company_name = company.name if company else None
        if not company_name and meta:
            company_name = meta.get("company_name") or meta.get("business_name")
        if not company_name:
            company_name = lead.title or "Target Prospect"

        contact_name = contact.full_name if contact else None
        contact_email = contact.email if contact else None
        contact_handle = None
        if contact:
            contact_handle = contact.instagram_username or contact.reddit_username
        if not contact_handle and meta:
            contact_handle = meta.get("handle") or meta.get("username")

        # 2. Source context
        primary_source_type = "WEB"
        source_url = None
        if sources and len(sources) > 0:
            src = sources[0]
            primary_source_type = src.source_type
            source_url = src.source_url
            if src.metadata_json and "observation" in src.metadata_json:
                obs = src.metadata_json["observation"]
                verified_observations.append(obs)
                evidence_list.append(
                    OutreachEvidenceModel(
                        claim=f"Observed on {primary_source_type}: {obs}",
                        source_url=source_url,
                        evidence_text=obs,
                        evidence_type="SOURCE_OBSERVATION",
                    )
                )

        # 3. Phase 3 Signals
        if signals:
            for sig in signals:
                verified_signals.append(sig.signal_type)
                claim_text = getattr(sig, "evidence", None) or f"Signal detected: {sig.signal_type}"
                evidence_list.append(
                    OutreachEvidenceModel(
                        claim=claim_text,
                        source_url=sig.source_url or source_url,
                        evidence_text=claim_text,
                        evidence_type="SIGNAL",
                        confidence=sig.confidence,
                    )
                )

        # 4. Phase 4 Website Research findings
        website_url = None
        website_findings: Dict[str, Any] = {}
        website_opportunities: Dict[str, Any] = {}

        if website_research:
            website_url = website_research.website_url
            tech_stack = website_research.technology_stack or {}
            cms = website_research.cms
            ecom = website_research.ecommerce_platform

            if cms:
                evidence_list.append(
                    OutreachEvidenceModel(
                        claim=f"Website built with {cms}",
                        source_url=website_url,
                        evidence_text=f"Detected CMS: {cms}",
                        evidence_type="TECHNOLOGY",
                    )
                )
            if ecom:
                evidence_list.append(
                    OutreachEvidenceModel(
                        claim=f"Storefront powered by {ecom}",
                        source_url=website_url,
                        evidence_text=f"Detected E-commerce: {ecom}",
                        evidence_type="TECHNOLOGY",
                    )
                )

            website_findings = {
                "cms": cms,
                "ecommerce_platform": ecom,
                "frontend": website_research.frontend_framework,
                "mobile_score": website_research.mobile_score,
                "ux_score": website_research.ux_score,
                "seo_score": website_research.seo_score,
                "conversion_score": website_research.conversion_score,
                "performance_score": website_research.performance_score,
                "negative_findings": website_research.negative_findings,
                "positive_findings": website_research.positive_findings,
            }

            # Map negative findings to pain points
            for neg in website_research.negative_findings or []:
                category = PainPointCategory.WEBSITE
                if "mobile" in neg.lower():
                    category = PainPointCategory.MOBILE_UX
                elif "speed" in neg.lower() or "slow" in neg.lower() or "performance" in neg.lower():
                    category = PainPointCategory.PERFORMANCE
                elif "seo" in neg.lower() or "meta" in neg.lower():
                    category = PainPointCategory.SEO
                elif "cta" in neg.lower() or "conversion" in neg.lower() or "checkout" in neg.lower():
                    category = PainPointCategory.CONVERSION

                pp = PainPoint(
                    category=category,
                    statement=neg,
                    evidence=f"Observed on public website {website_url}",
                    source_url=website_url,
                    confidence=0.9,
                    severity="MEDIUM",
                )
                pain_points.append(pp)
                evidence_list.append(
                    OutreachEvidenceModel(
                        claim=neg,
                        source_url=website_url,
                        evidence_text=f"Observed on public website {website_url}: {neg}",
                        evidence_type="WEBSITE_AUDIT",
                        confidence=0.9,
                    )
                )

            for rec in website_research.recommendations or []:
                opportunity_points.append(rec)

        # 5. Determine recommended channel & angle
        recommended_channel = cls._determine_channel(primary_source_type, contact_email, contact_handle)
        recommended_angle = cls._determine_angle(verified_signals, pain_points, meta)

        # 6. Service recommendation from CRM lead or default
        rec_service = lead.recommended_service or TechVerseService.BUSINESS_WEBSITE.value
        alt_services: List[str] = []
        if meta:
            if "service_matching" in meta:
                sm = meta["service_matching"]
                rec_service = sm.get("primary_service", rec_service)
                alt_services = sm.get("alternative_services", [])
            elif "recommended_service" in meta:
                rec_service = meta["recommended_service"]

        score_val = getattr(lead, "overall_score", 50)
        cat_val = "HOT" if score_val >= 90 else ("HIGH" if score_val >= 75 else ("GOOD" if score_val >= 60 else "MEDIUM"))

        return OutreachContext(
            lead_id=lead.id,
            company_name=company_name,
            company_id=company.id if company else None,
            contact_name=contact_name,
            contact_email=contact_email,
            contact_handle=contact_handle,
            source=primary_source_type,
            source_url=source_url,
            business_summary=lead.summary or meta.get("summary"),
            verified_observations=verified_observations,
            verified_signals=verified_signals,
            lead_score=score_val,
            lead_category=cat_val,
            recommended_service=rec_service,
            alternative_services=alt_services,
            website_url=website_url,
            website_findings=website_findings,
            website_opportunities=website_opportunities,
            pain_points=pain_points,
            opportunity_points=opportunity_points,
            decision_maker=contact_name,
            decision_maker_confidence=0.85 if contact_name else 0.0,
            recent_activity=verified_observations[0] if verified_observations else None,
            previous_outreach=previous_outreach or [],
            previous_replies=previous_replies or [],
            recommended_channel=recommended_channel,
            recommended_angle=recommended_angle,
            evidence=evidence_list,
            confidence=0.9,
        )

    @classmethod
    def _determine_channel(
        cls,
        source_type: str,
        contact_email: Optional[str],
        contact_handle: Optional[str],
    ) -> OutreachChannel:
        st = source_type.upper()
        if "INSTAGRAM" in st:
            return OutreachChannel.INSTAGRAM_DM
        if "REDDIT" in st:
            return OutreachChannel.REDDIT_REPLY
        if "LINKEDIN" in st:
            return OutreachChannel.LINKEDIN_MESSAGE
        if contact_email:
            return OutreachChannel.EMAIL
        if contact_handle and contact_handle.startswith("@"):
            return OutreachChannel.INSTAGRAM_DM
        return OutreachChannel.EMAIL

    @classmethod
    def _determine_angle(
        cls,
        signals: List[str],
        pain_points: List[PainPoint],
        metadata: Optional[Dict[str, Any]],
    ) -> OutreachAngle:
        sig_set = set(signals)
        if "BUSINESS_LAUNCH" in sig_set:
            return OutreachAngle.NEW_BUSINESS_LAUNCH
        if "ECOMMERCE_OPPORTUNITY" in sig_set:
            return OutreachAngle.ECOMMERCE
        if "POOR_MOBILE_UX" in sig_set:
            return OutreachAngle.MOBILE_UX
        if "WEBSITE_OUTDATED" in sig_set:
            return OutreachAngle.WEBSITE_REDESIGN
        if "WEBSITE_SLOW" in sig_set:
            return OutreachAngle.PERFORMANCE
        if "WEAK_CONVERSION" in sig_set:
            return OutreachAngle.CONVERSION
        if "WEAK_SEO" in sig_set:
            return OutreachAngle.SEO
        if "AI_AUTOMATION_REQUEST" in sig_set:
            return OutreachAngle.AI_AUTOMATION

        for pp in pain_points:
            if pp.category == PainPointCategory.MOBILE_UX:
                return OutreachAngle.MOBILE_UX
            if pp.category == PainPointCategory.CONVERSION:
                return OutreachAngle.CONVERSION
            if pp.category == PainPointCategory.PERFORMANCE:
                return OutreachAngle.PERFORMANCE

        return OutreachAngle.WEBSITE_IMPROVEMENT
