from packages.shared_types.outreach import OutreachChannel
from services.api.app.agents.outreach.evidence_validator import EvidenceValidator
from services.api.app.agents.outreach.outreach_models import (
    MessageValidationResult,
    OutreachContext,
)
from services.api.app.services.outreach_quality import OutreachQualityScorer


class MessageValidator:
    """Validates complete message draft against evidence, channel constraints, and quality standards."""

    @classmethod
    def validate_draft(
        cls,
        body: str,
        context: OutreachContext,
        channel: OutreachChannel,
    ) -> MessageValidationResult:
        # 1. Evidence validation
        ev_valid, ev_errors, ev_warnings, ev_coverage = EvidenceValidator.validate_evidence_alignment(
            body=body,
            context=context,
        )

        # 2. Quality and channel bounds scoring
        score, all_errors, all_warnings = OutreachQualityScorer.calculate_score(
            body=body,
            context=context,
            channel=channel,
            evidence_coverage=ev_coverage,
            validation_errors=ev_errors,
        )
        all_warnings.extend(ev_warnings)

        # 3. Overall validity: no errors and score >= 75
        valid = (len(all_errors) == 0) and (score >= 75)

        return MessageValidationResult(
            valid=valid,
            score=score,
            errors=all_errors,
            warnings=all_warnings,
            unsupported_claims=ev_errors,
            evidence_coverage=ev_coverage,
            personalization_score=min(100, int(score * 1.0)),
        )
