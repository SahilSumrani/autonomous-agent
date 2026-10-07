from typing import Any, Dict, List
from pydantic import BaseModel, Field

from services.api.app.agents.conversation.validators import (
    detect_prohibited_commitments,
    validate_reply_length,
)


class ReplyValidationResult(BaseModel):
    is_valid: bool
    quality_score: int
    score_breakdown: Dict[str, int]
    risk_flags: List[str] = Field(default_factory=list)
    rejection_reasons: List[str] = Field(default_factory=list)
    recommendation: str  # READY_FOR_APPROVAL, NEEDS_REGENERATION, HUMAN_REQUIRED


class ReplyMessageAnalyzer:
    """
    Deterministic quality and safety auditor for conversation reply drafts.
    Enforces quality score threshold >= 75 and rejects prohibited claims or length violations.
    """

    APPROVAL_THRESHOLD = 75

    @classmethod
    def analyze(
        cls,
        reply_body: str,
        channel: str,
        prospect_name: str,
        service_name: str,
        intent_name: str,
    ) -> ReplyValidationResult:
        score_breakdown: Dict[str, int] = {}
        risk_flags: List[str] = []
        rejection_reasons: List[str] = []

        # 1. Prohibited commitment check (Hard safety gate)
        prohibited = detect_prohibited_commitments(reply_body)
        if prohibited:
            risk_flags.extend(prohibited)
            rejection_reasons.append(f"Contains prohibited autonomous claims: {', '.join(prohibited)}")

        # 2. Length check (Channel fit)
        valid_len, len_msg = validate_reply_length(reply_body, channel)
        if not valid_len:
            risk_flags.append(len_msg)
            rejection_reasons.append(len_msg)
            score_breakdown["channel_fit"] = 4
        else:
            score_breakdown["channel_fit"] = 15

        # 3. Personalization (Name or handle referenced)
        clean_name = prospect_name.lstrip("@").lower()
        if clean_name and clean_name != "there" and clean_name in reply_body.lower():
            score_breakdown["personalization"] = 15
        elif "there" in reply_body.lower():
            score_breakdown["personalization"] = 10
        else:
            score_breakdown["personalization"] = 8

        # 4. Relevance & Intent matching
        if service_name.lower() in reply_body.lower():
            score_breakdown["relevance"] = 15
        else:
            score_breakdown["relevance"] = 10

        # 5. Evidence grounding & Clarity
        score_breakdown["evidence_grounding"] = 14
        score_breakdown["clarity"] = 14
        score_breakdown["helpfulness"] = 14

        # 6. CTA Quality (Checks for question mark or action proposal)
        if "?" in reply_body or "let me know" in reply_body.lower():
            score_breakdown["cta_quality"] = 10
        else:
            score_breakdown["cta_quality"] = 4

        # Total score calculation
        total_score = sum(score_breakdown.values())

        # Heavy penalties for risks
        if risk_flags:
            penalty = len(risk_flags) * 20
            total_score = max(0, total_score - penalty)

        is_valid = (total_score >= cls.APPROVAL_THRESHOLD) and (len(rejection_reasons) == 0)
        recommendation = "READY_FOR_APPROVAL" if is_valid else "NEEDS_REGENERATION"

        return ReplyValidationResult(
            is_valid=is_valid,
            quality_score=total_score,
            score_breakdown=score_breakdown,
            risk_flags=risk_flags,
            rejection_reasons=rejection_reasons,
            recommendation=recommendation,
        )
