from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from packages.shared_types.crm import SignalType
from services.api.app.agents.research.evidence_collector import EvidenceCollector
from services.api.app.agents.research.page_analyzer import PageAnalyzer
from services.api.app.agents.research.research_models import (
    AuditScores,
    EvidenceCategory,
    PageAnalysisResult,
    ResearchDataSource,
    ResearchEvidence,
    ResearchStatus,
    TechnologyFinding,
    WebsiteOpportunityBreakdown,
    WebsiteResearchSummary,
)
from services.api.app.agents.research.technology_detector import TechnologyDetector
from services.api.app.agents.research.validators import (
    SSRFValidationError,
    validate_and_sanitize_target_url,
)
from services.api.app.services.research_scoring import ResearchScoringEngine
from services.api.app.services.service_matching import ServiceMatchingEngine
from services.api.app.services.website_audit import WebsiteAuditEngine


class ResearchEngine:
    """Orchestrates deep website research, page audits, stack discovery, and opportunity scoring."""

    @classmethod
    def execute_research(
        cls,
        website_url: str,
        pages_data: Optional[List[Dict[str, Any]]] = None,
        company_name: Optional[str] = None,
        data_source: Optional[str] = None,
    ) -> Dict[str, Any]:
        sanitized_url = validate_and_sanitize_target_url(website_url)
        evidence_collector = EvidenceCollector()

        # If pages_data is empty or not provided, real research is unavailable.
        # NEVER invent data or substitute fake mock pages.
        if not pages_data:
            business_title = company_name or urlparse(sanitized_url).netloc
            scores = AuditScores(
                website_health_score=0,
                performance_score=0,
                mobile_score=0,
                ux_score=0,
                seo_score=0,
                conversion_score=0,
                accessibility_score=0,
            )
            opp_breakdown = WebsiteOpportunityBreakdown(
                performance_opportunity=0,
                mobile_opportunity=0,
                ux_opportunity=0,
                seo_opportunity=0,
                conversion_opportunity=0,
                ecommerce_opportunity=0,
                tech_modernization_opportunity=0,
                total_opportunity_score=0,
                reasons=[],
            )
            research_summary = WebsiteResearchSummary(
                website_status=ResearchStatus.RESEARCH_UNAVAILABLE.value,
                business_summary=f"Public website resolved at {sanitized_url}, but page content is unavailable.",
                technology_summary="None observed",
                strengths=[],
                weaknesses=[],
                opportunities=[],
                critical_findings=[],
                recommended_service="None",
                alternative_services=[],
                evidence=[],
                confidence=0.0,
            )
            return {
                "status": ResearchStatus.RESEARCH_UNAVAILABLE.value,
                "data_source": ResearchDataSource.UNAVAILABLE_DATA.value,
                "website_url": sanitized_url,
                "pages_analyzed": 0,
                "pages_failed": 0,
                "technology_stack": [],
                "cms": None,
                "frontend_framework": None,
                "backend_technology": None,
                "analytics_tools": [],
                "payment_provider": None,
                "hosting_provider": None,
                "cdn": None,
                "ecommerce_platform": None,
                "scores": scores,
                "opportunity_breakdown": opp_breakdown,
                "positive_findings": [],
                "negative_findings": [],
                "recommendations": [],
                "summary": f"Research unavailable for {business_title}: no observed or supplied page content.",
                "research_summary": research_summary,
                "analyzed_pages": [],
                "generated_signals": [],
                "all_evidence": [],
                "confidence": 0.0,
            }

        # Resolve data source category: OBSERVED_DATA vs USER_SUPPLIED_DATA
        effective_data_source = data_source or (
            ResearchDataSource.OBSERVED_DATA.value
            if any(p.get("source_type") in ("OBSERVED_DATA", "BROWSER_OBSERVATION") or p.get("is_observed") for p in pages_data)
            else ResearchDataSource.USER_SUPPLIED_DATA.value
        )

        # 1. Analyze all pages
        analyzed_pages: List[PageAnalysisResult] = []
        all_tech_findings: List[TechnologyFinding] = []

        for p_data in pages_data:
            url = p_data.get("url", sanitized_url)
            html = p_data.get("html", "")
            text = p_data.get("visible_text", "")
            links = p_data.get("links", [])
            headers = p_data.get("headers", {})

            # Technology detection on this page
            tech_findings = TechnologyDetector.detect_technologies(
                html_content=html,
                scripts=p_data.get("scripts", []),
                headers=headers,
            )
            for tf in tech_findings:
                if tf not in all_tech_findings:
                    all_tech_findings.append(tf)
                    evidence_collector.add_evidence(
                        category=EvidenceCategory.TECHNOLOGY.value,
                        statement=f"Detected {tf.technology} ({tf.category}): {tf.evidence}",
                        source_url=url,
                        source_type="HTML_ARTIFACT",
                        confidence=tf.confidence,
                    )

            # Analyze page layout, SEO, mobile, and conversion
            page_res = PageAnalyzer.analyze_page(
                url=url,
                html_content=html,
                visible_text=text,
                links=links,
            )
            analyzed_pages.append(page_res)
            for ev in page_res.evidence:
                evidence_collector.add_evidence(
                    category=ev.category,
                    statement=ev.statement,
                    source_url=ev.source_url,
                    source_type=ev.source_type,
                    confidence=ev.confidence,
                )

        # 2. Run Audit Aggregator
        audit_res = WebsiteAuditEngine.audit_pages(
            pages=analyzed_pages,
            tech_findings=all_tech_findings,
        )
        scores: AuditScores = audit_res["scores"]
        ecommerce_detected = audit_res["ecommerce_detected"]
        ecommerce_platform = audit_res["ecommerce_platform"]

        # 3. Calculate Website Opportunity Score (0-100)
        opp_breakdown: WebsiteOpportunityBreakdown = ResearchScoringEngine.calculate_opportunity_score(
            audit_scores=scores,
            has_ecommerce_potential=ecommerce_detected,
            tech_findings=all_tech_findings,
        )

        # 4. Synthesize Technology Stack
        cms = None
        frontend = None
        backend = None
        analytics: List[str] = []
        cdn = None
        payment = None

        for tf in all_tech_findings:
            if tf.category == "CMS" and not cms:
                cms = tf.technology
            elif tf.category == "FRONTEND" and not frontend:
                frontend = tf.technology
            elif tf.category == "BACKEND" and not backend:
                backend = tf.technology
            elif tf.category == "ANALYTICS" and tf.technology not in analytics:
                analytics.append(tf.technology)
            elif tf.category == "CDN_INFRASTRUCTURE" and not cdn:
                cdn = tf.technology
            elif tf.category == "ECOMMERCE" and not ecommerce_platform:
                ecommerce_platform = tf.technology

        # 5. Determine Recommended TechVerse Service Match
        service_match = ServiceMatchingEngine.match_service(
            signals=[
                SignalType.ECOMMERCE_OPPORTUNITY if ecommerce_detected else SignalType.WEBSITE_OUTDATED
            ],
            business_context=f"Website opportunity score: {opp_breakdown.total_opportunity_score}/100 with {scores.website_health_score}/100 technical health",
        )

        # 6. Generate Website Signals to feed into CRM
        generated_signals: List[Dict[str, Any]] = []
        if ecommerce_detected:
            generated_signals.append({
                "signal_type": SignalType.ECOMMERCE_OPPORTUNITY.value,
                "confidence": 0.95,
                "evidence": f"Audited website shows active product presence or {ecommerce_platform or 'ecommerce'} platform.",
                "source_url": sanitized_url,
            })
        if scores.mobile_score < 65:
            generated_signals.append({
                "signal_type": SignalType.POOR_MOBILE_UX.value,
                "confidence": 0.92,
                "evidence": "Website missing mobile viewport configuration or exhibits horizontal layout friction.",
                "source_url": sanitized_url,
            })
        if scores.conversion_score < 65:
            generated_signals.append({
                "signal_type": SignalType.WEAK_CONVERSION.value,
                "confidence": 0.90,
                "evidence": "Website lacks prominent calls-to-action or direct customer lead capture.",
                "source_url": sanitized_url,
            })
        if scores.performance_score < 65:
            generated_signals.append({
                "signal_type": SignalType.WEBSITE_SLOW.value,
                "confidence": 0.88,
                "evidence": "Heavy script load and unoptimized assets create observable performance bottlenecks.",
                "source_url": sanitized_url,
            })
        if scores.seo_score < 65:
            generated_signals.append({
                "signal_type": SignalType.WEAK_SEO.value,
                "confidence": 0.88,
                "evidence": "Missing critical SEO metadata (titles, descriptions, or header structure).",
                "source_url": sanitized_url,
            })
        if opp_breakdown.total_opportunity_score >= 60 and not ecommerce_detected:
            generated_signals.append({
                "signal_type": SignalType.WEBSITE_OUTDATED.value,
                "confidence": 0.91,
                "evidence": f"Technical audit indicates outdated UX and structure (Opportunity score: {opp_breakdown.total_opportunity_score}/100).",
                "source_url": sanitized_url,
            })

        # 7. Summary
        business_title = company_name or urlparse(sanitized_url).netloc
        summary = (
            f"Technical research completed for {business_title}. "
            f"Audited {len(analyzed_pages)} pages. "
            f"Overall health: {scores.website_health_score}/100, Opportunity: {opp_breakdown.total_opportunity_score}/100. "
            f"Identified {len(audit_res['negative_findings'])} key optimization areas."
        )

        research_summary = WebsiteResearchSummary(
            website_status="ACTIVE",
            business_summary=f"Commercial website operated by {business_title}",
            technology_summary=f"CMS: {cms or 'None'}, Frontend: {frontend or 'Standard'}, E-commerce: {ecommerce_platform or 'None'}",
            strengths=audit_res["positive_findings"],
            weaknesses=audit_res["negative_findings"],
            opportunities=opp_breakdown.reasons,
            critical_findings=audit_res["negative_findings"][:3],
            recommended_service=service_match.recommended_service.value,
            alternative_services=[s.value for s in service_match.alternative_services],
            evidence=evidence_collector.to_dict_list(),
            confidence=0.92,
        )

        return {
            "status": ResearchStatus.COMPLETED.value,
            "data_source": effective_data_source,
            "website_url": sanitized_url,
            "pages_analyzed": len(analyzed_pages),
            "pages_failed": 0,
            "technology_stack": [tf.model_dump() for tf in all_tech_findings],
            "cms": cms,
            "frontend_framework": frontend,
            "backend_technology": backend,
            "analytics_tools": analytics,
            "payment_provider": payment,
            "hosting_provider": None,
            "cdn": cdn,
            "ecommerce_platform": ecommerce_platform,
            "scores": scores,
            "opportunity_breakdown": opp_breakdown,
            "positive_findings": audit_res["positive_findings"],
            "negative_findings": audit_res["negative_findings"],
            "recommendations": audit_res["recommendations"],
            "summary": summary,
            "research_summary": research_summary,
            "analyzed_pages": analyzed_pages,
            "generated_signals": generated_signals,
            "all_evidence": evidence_collector.get_all(),
            "confidence": 0.92,
        }
