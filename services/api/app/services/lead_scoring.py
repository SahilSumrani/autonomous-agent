import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from packages.shared_types.crm import (
    NextAction,
    ScoreCategory,
    SignalType,
    TechVerseService,
)
from services.api.app.agents.signals.engine import DetectedSignal
from services.api.app.services.service_matching import ServiceMatchingEngine


class ScoreBreakdown(BaseModel):
    """Detailed score distribution across 7 audited dimensions (Max 100)."""
    buying_intent: int = Field(default=0, ge=0, le=30)
    service_match: int = Field(default=0, ge=0, le=20)
    business_quality: int = Field(default=0, ge=0, le=15)
    budget_potential: int = Field(default=0, ge=0, le=15)
    decision_maker: int = Field(default=0, ge=0, le=10)
    website_opportunity: int = Field(default=0, ge=0, le=5)
    recent_activity: int = Field(default=0, ge=0, le=5)
    overall: Optional[int] = Field(default=None, ge=0, le=100)

    def total(self) -> int:
        return self.overall if self.overall is not None else (
            self.buying_intent
            + self.service_match
            + self.business_quality
            + self.budget_potential
            + self.decision_maker
            + self.website_opportunity
            + self.recent_activity
        )

    def model_post_init(self, __context: Any) -> None:
        if self.overall is None:
            self.overall = min(100, (
                self.buying_intent
                + self.service_match
                + self.business_quality
                + self.budget_potential
                + self.decision_maker
                + self.website_opportunity
                + self.recent_activity
            ))


class LeadQualification(BaseModel):
    """Holistic qualification and next-action recommendation for a lead."""
    lead_id: Optional[uuid.UUID] = None
    qualified: bool
    overall_score: int = Field(..., ge=0, le=100)
    category: ScoreCategory
    score_breakdown: ScoreBreakdown
    score_reasons: List[str]
    positive_factors: List[str]
    negative_factors: List[str]
    recommended_service: TechVerseService
    alternative_services: List[TechVerseService]
    recommended_next_action: NextAction
    confidence: float = Field(..., ge=0.0, le=1.0)


class LeadScoringEngine:
    """Deterministic lead qualification and scoring engine."""

    @classmethod
    def calculate_category(cls, score: int) -> ScoreCategory:
        if score >= 90:
            return ScoreCategory.HOT
        elif score >= 75:
            return ScoreCategory.HIGH
        elif score >= 60:
            return ScoreCategory.GOOD
        elif score >= 40:
            return ScoreCategory.MEDIUM
        return ScoreCategory.LOW

    score_to_category = calculate_category

    @classmethod
    def determine_next_action(cls, score: int, is_founder: bool = False) -> NextAction:
        if score >= 90:
            return NextAction.REQUEST_APPROVAL
        elif score >= 75:
            return NextAction.PREPARE_OUTREACH
        elif score >= 60:
            return NextAction.RESEARCH_MORE
        elif score >= 40:
            return NextAction.MONITOR
        return NextAction.IGNORE

    @classmethod
    def evaluate_lead(
        cls,
        signals: List[DetectedSignal],
        business_name: Optional[str] = None,
        job_title: Optional[str] = None,
        has_website: bool = False,
        website_audit_issues: Optional[List[str]] = None,
        detected_at: Optional[datetime] = None,
        lead_id: Optional[uuid.UUID] = None,
        text_corpus: Optional[str] = None,
        profile_bio: Optional[str] = None,
    ) -> LeadQualification:
        corpus = f"{text_corpus or ''} {profile_bio or ''}".lower()
        if not job_title and corpus:
            if any(role in corpus for role in ["founder", "owner", "ceo", "co-founder", "managing director"]):
                job_title = "Founder"
            elif any(role in corpus for role in ["head", "director", "vp", "lead", "manager"]):
                job_title = "Management Lead"

        if not business_name and corpus:
            if any(word in corpus for word in ["brand", "company", "studio", "boutique", "startup", "clinic", "shop", "store"]):
                business_name = "Commercial Business"

        signal_types = [s.signal_type for s in signals]
        reasons: List[str] = []
        positive_factors: List[str] = []
        negative_factors: List[str] = []

        # 1. Buying Intent (Max 30)
        buying_intent = 0
        if any(s in signal_types for s in [SignalType.WEBSITE_REQUEST, SignalType.APP_DEVELOPMENT_REQUEST, SignalType.AI_AUTOMATION_REQUEST]):
            buying_intent = 29
            reasons.append("+29 Explicit request for development or automation service")
            positive_factors.append("Explicit service request detected in public posting")
        elif any(s in signal_types for s in [SignalType.HIRING_DEVELOPER, SignalType.HIRING_DESIGNER]):
            buying_intent = 26
            reasons.append("+26 Active hiring postings for technical / design roles")
            positive_factors.append("Active technical recruitment")
        elif any(s in signal_types for s in [SignalType.WEBSITE_OUTDATED, SignalType.ECOMMERCE_OPPORTUNITY]):
            buying_intent = 24
            reasons.append("+24 High-intent requirement for rebuild or storefront")
            positive_factors.append("Clear digital rebuild or e-commerce requirement")
        elif SignalType.BUSINESS_LAUNCH in signal_types:
            buying_intent = 20
            reasons.append("+20 New business launch milestone")
            positive_factors.append("Commercial venture launch")
        elif any(s in signal_types for s in [SignalType.GROWTH_SIGNAL, SignalType.BUSINESS_EXPANSION]):
            buying_intent = 15
            reasons.append("+15 Business expansion or growth indicators")
            positive_factors.append("Commercial expansion")
        else:
            buying_intent = 0
            negative_factors.append("No active commercial or buying signal identified")

        # 2. Service Match (Max 20)
        match_result = ServiceMatchingEngine.match_service(signal_types, business_name or text_corpus)
        if any(s in signal_types for s in [
            SignalType.WEBSITE_REQUEST, SignalType.WEBSITE_OUTDATED, SignalType.APP_DEVELOPMENT_REQUEST,
            SignalType.AI_AUTOMATION_REQUEST, SignalType.ECOMMERCE_OPPORTUNITY
        ]):
            service_match = 20
            reasons.append(f"+20 Direct alignment with TechVerse core offering: {match_result.recommended_service.value}")
            positive_factors.append(f"Direct match for {match_result.recommended_service.value}")
        elif SignalType.BUSINESS_LAUNCH in signal_types:
            service_match = 18
            reasons.append("+18 Launching business requires digital foundation")
            positive_factors.append("Business website alignment")
        else:
            service_match = 5
            negative_factors.append("Weak service fit with primary core offerings")

        # 3. Business Quality (Max 15)
        if business_name and len(business_name.strip()) > 2:
            business_quality = 13
            reasons.append("+13 Verified active business entity with distinct identity")
            positive_factors.append("Identified business entity")
        else:
            business_quality = 6
            reasons.append("+6 Generic or individual creator profile without branded entity")
            negative_factors.append("Unverified corporate identity")

        # 4. Budget Potential (Max 15)
        if SignalType.RECENT_FUNDING in signal_types or SignalType.BUSINESS_EXPANSION in signal_types:
            budget_potential = 14
            reasons.append("+14 Observable capital: Recent funding or multi-location expansion")
            positive_factors.append("Verified commercial capital availability")
        elif any(s in signal_types for s in [SignalType.HIRING_DEVELOPER, SignalType.GROWTH_SIGNAL]):
            budget_potential = 12
            reasons.append("+12 Active commercial hiring budget")
            positive_factors.append("Recruitment capital")
        elif SignalType.BUSINESS_LAUNCH in signal_types or has_website:
            budget_potential = 9
            reasons.append("+9 Operational commercial baseline")
        else:
            budget_potential = 4
            reasons.append("+4 Conservative budget baseline (no funding or payroll evidence)")
            negative_factors.append("Conservative budget assumptions applied")

        # 5. Decision Maker (Max 10)
        clean_title = (job_title or "").lower()
        if any(role in clean_title for role in ["founder", "owner", "ceo", "co-founder", "principal", "managing director"]):
            decision_maker = 10
            reasons.append(f"+10 Primary decision maker identified: {job_title}")
            positive_factors.append("Direct contact with founder / executive")
        elif any(role in clean_title for role in ["head", "director", "vp", "lead", "manager"]):
            decision_maker = 7
            reasons.append(f"+7 Senior operational lead identified: {job_title}")
            positive_factors.append("Senior management contact")
        else:
            decision_maker = 2
            reasons.append("+2 Individual or unspecified decision maker role")
            negative_factors.append("Decision maker not yet verified")

        # 6. Website Opportunity (Max 5)
        if website_audit_issues and len(website_audit_issues) > 0:
            website_opportunity = 5
            reasons.append(f"+5 Concrete website improvement opportunities observed ({len(website_audit_issues)} issues)")
            positive_factors.append(f"Identified {len(website_audit_issues)} website UX/performance issues")
        elif not has_website and SignalType.BUSINESS_LAUNCH in signal_types:
            website_opportunity = 4
            reasons.append("+4 New business currently lacking an online website")
            positive_factors.append("Greenfield website opportunity")
        else:
            website_opportunity = 2
            reasons.append("+2 Standard digital baseline")

        # 7. Recent Activity (Max 5)
        now = datetime.now(timezone.utc)
        activity_date = detected_at or now
        days_ago = max(0, (now - activity_date).days)
        if days_ago <= 7:
            recent_activity = 5
            reasons.append("+5 High recency: Observed within past 7 days")
            positive_factors.append("Fresh activity (within 7 days)")
        elif days_ago <= 30:
            recent_activity = 3
            reasons.append("+3 Active within past month")
        else:
            recent_activity = 1
            reasons.append("+1 Activity older than 30 days")
            negative_factors.append("Activity is more than 30 days old")

        # Total Calculation
        overall = min(100, max(0, (
            buying_intent
            + service_match
            + business_quality
            + budget_potential
            + decision_maker
            + website_opportunity
            + recent_activity
        )))

        breakdown = ScoreBreakdown(
            buying_intent=buying_intent,
            service_match=service_match,
            business_quality=business_quality,
            budget_potential=budget_potential,
            decision_maker=decision_maker,
            website_opportunity=website_opportunity,
            recent_activity=recent_activity,
            overall=overall,
        )

        category = cls.calculate_category(overall)
        next_action = cls.determine_next_action(overall, is_founder=(decision_maker == 10))

        confidence = max(0.5, min(0.98, round(overall / 100.0, 2)))

        return LeadQualification(
            lead_id=lead_id,
            qualified=(overall >= 60),
            overall_score=overall,
            category=category,
            score_breakdown=breakdown,
            score_reasons=reasons,
            positive_factors=positive_factors,
            negative_factors=negative_factors,
            recommended_service=match_result.recommended_service,
            alternative_services=match_result.alternative_services,
            recommended_next_action=next_action,
            confidence=confidence,
        )
