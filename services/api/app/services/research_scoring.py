from typing import List, Optional
from services.api.app.agents.research.research_models import AuditScores, TechnologyFinding, WebsiteOpportunityBreakdown


class ResearchScoringEngine:
    """
    Deterministic scoring engine calculating the Website Opportunity Score (0-100).
    Higher opportunity indicates greater value in redesigning, rebuilding, or optimizing.
    """

    @classmethod
    def calculate_opportunity_score(
        cls,
        audit_scores: AuditScores,
        has_ecommerce_potential: bool = False,
        tech_findings: Optional[List[TechnologyFinding]] = None,
    ) -> WebsiteOpportunityBreakdown:
        reasons: List[str] = []

        # 1. Performance Opportunity (Max 20)
        # Inverted relative to performance score
        if audit_scores.performance_score < 50:
            perf_opp = 20
            reasons.append("+20 Critical performance lag and asset bloat")
        elif audit_scores.performance_score < 70:
            perf_opp = 14
            reasons.append("+14 Noticeable performance bottlenecks")
        elif audit_scores.performance_score < 85:
            perf_opp = 7
            reasons.append("+7 Moderate performance optimization potential")
        else:
            perf_opp = 0

        # 2. Mobile Opportunity (Max 15)
        if audit_scores.mobile_score < 50:
            mobile_opp = 15
            reasons.append("+15 Severe mobile UX flaws or missing viewport")
        elif audit_scores.mobile_score < 70:
            mobile_opp = 10
            reasons.append("+10 Sub-optimal mobile layout responsiveness")
        elif audit_scores.mobile_score < 85:
            mobile_opp = 5
            reasons.append("+5 Minor mobile improvements possible")
        else:
            mobile_opp = 0

        # 3. UX Opportunity (Max 15)
        if audit_scores.ux_score < 50:
            ux_opp = 15
            reasons.append("+15 Poor navigation structure or visual hierarchy")
        elif audit_scores.ux_score < 70:
            ux_opp = 10
            reasons.append("+10 User friction in navigation and layout")
        elif audit_scores.ux_score < 85:
            ux_opp = 5
            reasons.append("+5 Potential for UX modernization")
        else:
            ux_opp = 0

        # 4. SEO Opportunity (Max 15)
        if audit_scores.seo_score < 50:
            seo_opp = 15
            reasons.append("+15 Deficient SEO metadata and missing heading hierarchy")
        elif audit_scores.seo_score < 70:
            seo_opp = 10
            reasons.append("+10 SEO gaps in titles, descriptions, and structure")
        elif audit_scores.seo_score < 85:
            seo_opp = 5
            reasons.append("+5 On-page SEO tuning potential")
        else:
            seo_opp = 0

        # 5. Conversion Opportunity (Max 15)
        if audit_scores.conversion_score < 50:
            conv_opp = 15
            reasons.append("+15 Missing clear calls-to-action and direct contact channels")
        elif audit_scores.conversion_score < 70:
            conv_opp = 10
            reasons.append("+10 Weak conversion funnel and limited proof signals")
        elif audit_scores.conversion_score < 85:
            conv_opp = 5
            reasons.append("+5 Conversion rate optimization opportunities")
        else:
            conv_opp = 0

        # 6. E-commerce Opportunity (Max 10)
        ecomm_opp = 0
        if has_ecommerce_potential:
            ecomm_opp = 10
            reasons.append("+10 High-value e-commerce storefront expansion opportunity")
        elif tech_findings and any(t.category == "ECOMMERCE" for t in tech_findings):
            ecomm_opp = 6
            reasons.append("+6 Existing e-commerce presence ripe for optimization")

        # 7. Technology Modernization (Max 10)
        tech_opp = 0
        tech_names = [t.technology.lower() for t in (tech_findings or [])]
        if any(legacy in tech_names for legacy in ["php", "magento", "wordpress", "wix"]):
            tech_opp = 10
            reasons.append("+10 Legacy or template-constrained stack ripe for modern Next.js/React rebuild")
        elif not tech_findings:
            tech_opp = 5
            reasons.append("+5 Basic custom or unoptimized stack")
        else:
            tech_opp = 2

        total = perf_opp + mobile_opp + ux_opp + seo_opp + conv_opp + ecomm_opp + tech_opp
        total = max(0, min(100, total))

        return WebsiteOpportunityBreakdown(
            performance_opportunity=perf_opp,
            mobile_opportunity=mobile_opp,
            ux_opportunity=ux_opp,
            seo_opportunity=seo_opp,
            conversion_opportunity=conv_opp,
            ecommerce_opportunity=ecomm_opp,
            tech_modernization_opportunity=tech_opp,
            total_opportunity_score=total,
            reasons=reasons,
        )
