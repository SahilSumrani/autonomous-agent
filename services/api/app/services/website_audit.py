from typing import Any, Dict, List, Optional
from services.api.app.agents.research.research_models import AuditScores, PageAnalysisResult, TechnologyFinding


class WebsiteAuditEngine:
    """Aggregates multi-page findings and computes overall technical category health scores."""

    @classmethod
    def audit_pages(
        cls,
        pages: List[PageAnalysisResult],
        tech_findings: Optional[List[TechnologyFinding]] = None,
    ) -> Dict[str, Any]:
        if not pages:
            return {
                "scores": AuditScores(
                    website_health_score=0,
                    performance_score=0,
                    mobile_score=0,
                    ux_score=0,
                    seo_score=0,
                    conversion_score=0,
                    accessibility_score=0,
                ),
                "positive_findings": [],
                "negative_findings": [],
                "recommendations": [],
                "ecommerce_detected": False,
                "ecommerce_platform": None,
            }

        # 1. Performance calculation (starts at 100, deducted per observable flaw)
        perf = 95
        perf_deductions = 0
        for p in pages:
            if any("heavy script" in obs.lower() for obs in p.performance_observations):
                perf_deductions += 15
        perf = max(20, min(100, perf - perf_deductions))

        # 2. Mobile score
        mobile = 95
        mobile_deductions = 0
        for p in pages:
            if any("missing viewport" in obs.lower() for obs in p.mobile_observations):
                mobile_deductions += 40
            if any("overflow" in obs.lower() or "fixed desktop" in obs.lower() for obs in p.mobile_observations):
                mobile_deductions += 25
        mobile = max(15, min(100, mobile - mobile_deductions))

        # 3. UX score
        ux = 90
        ux_deductions = 0
        for p in pages:
            if any("no standard <nav>" in obs.lower() or "missing navigation" in obs.lower() for obs in p.ux_observations):
                ux_deductions += 30
        ux = max(20, min(100, ux - ux_deductions))

        # 4. SEO score
        seo = 95
        seo_deductions = 0
        for p in pages:
            if any("missing <title>" in obs.lower() for obs in p.seo_observations):
                seo_deductions += 25
            if any("missing meta description" in obs.lower() for obs in p.seo_observations):
                seo_deductions += 15
            if any("missing h1" in obs.lower() for obs in p.seo_observations):
                seo_deductions += 15
        seo = max(20, min(100, seo - seo_deductions))

        # 5. Conversion score
        conversion = 90
        conv_deductions = 0
        has_any_cta = any(p.has_cta for p in pages)
        has_any_contact = any(p.has_contact_form or p.has_email or p.has_phone for p in pages)
        has_any_proof = any(p.has_social_proof for p in pages)

        if not has_any_cta:
            conv_deductions += 35
        if not has_any_contact:
            conv_deductions += 25
        if not has_any_proof:
            conv_deductions += 15
        conversion = max(15, min(100, conversion - conv_deductions))

        # 6. Accessibility score
        accessibility = 85
        # 7. Overall health score
        health = int((perf * 0.2) + (mobile * 0.2) + (ux * 0.15) + (seo * 0.2) + (conversion * 0.15) + (accessibility * 0.1))

        # Compile positive/negative findings
        positives: List[str] = []
        negatives: List[str] = []
        recommendations: List[str] = []

        if has_any_cta:
            positives.append("Clear call-to-action buttons present on site.")
        else:
            negatives.append("No prominent calls-to-action detected across audited pages.")
            recommendations.append("Implement prominent, high-converting CTAs across primary landing pages.")

        if has_any_contact:
            positives.append("Direct contact and lead capture mechanisms present.")
        else:
            negatives.append("Missing direct lead capture forms or contact channels.")
            recommendations.append("Add interactive contact and inquiry forms.")

        if mobile < 65:
            negatives.append("Mobile usability deficits or missing viewport meta configurations detected.")
            recommendations.append("Full mobile-first responsive redesign to capture mobile visitors.")
        else:
            positives.append("Mobile responsiveness configured properly.")

        if seo < 70:
            negatives.append("Missing essential SEO metadata (titles, meta descriptions, or H1 structure).")
            recommendations.append("Restructure SEO metadata, schema markup, and heading hierarchy.")

        if perf < 70:
            negatives.append("High script load and performance bottlenecks impacting page speed.")
            recommendations.append("Optimize assets, defer non-critical scripts, and implement CDN caching.")

        # E-commerce detection
        ecommerce_detected = any(p.has_product_catalog or p.has_checkout for p in pages)
        ecommerce_platform = None
        if tech_findings:
            for t in tech_findings:
                if t.category == "ECOMMERCE":
                    ecommerce_detected = True
                    ecommerce_platform = t.technology
                    break

        if ecommerce_detected and not any(p.has_checkout for p in pages):
            negatives.append("Product catalog present but lacking streamlined direct checkout pathway.")
            recommendations.append("Integrate an end-to-end modern e-commerce checkout experience.")

        scores = AuditScores(
            website_health_score=health,
            performance_score=perf,
            mobile_score=mobile,
            ux_score=ux,
            seo_score=seo,
            conversion_score=conversion,
            accessibility_score=accessibility,
        )

        return {
            "scores": scores,
            "positive_findings": positives,
            "negative_findings": negatives,
            "recommendations": recommendations,
            "ecommerce_detected": ecommerce_detected,
            "ecommerce_platform": ecommerce_platform,
        }
