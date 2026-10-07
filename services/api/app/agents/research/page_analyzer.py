import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from services.api.app.agents.research.research_models import (
    EvidenceCategory,
    PageAnalysisResult,
    PageType,
    ResearchEvidence,
)
from services.api.app.agents.research.validators import sanitize_untrusted_page_content


class PageAnalyzer:
    """Analyzes observable page content, DOM features, conversion elements, and technical health."""

    @classmethod
    def classify_page_type(cls, url: str) -> str:
        path = urlparse(url).path.lower().rstrip("/")
        if not path or path == "":
            return PageType.HOMEPAGE.value
        if any(seg in path for seg in ["about", "our-story", "who-we-are"]):
            return PageType.ABOUT.value
        if any(seg in path for seg in ["service", "what-we-do"]):
            return PageType.SERVICES.value
        if any(seg in path for seg in ["product", "collection"]):
            return PageType.PRODUCTS.value
        if any(seg in path for seg in ["pricing", "plan"]):
            return PageType.PRICING.value
        if any(seg in path for seg in ["shop", "store", "catalog"]):
            return PageType.SHOP.value
        if any(seg in path for seg in ["contact", "reach-us"]):
            return PageType.CONTACT.value
        if any(seg in path for seg in ["portfolio", "work"]):
            return PageType.PORTFOLIO.value
        if any(seg in path for seg in ["case-stud"]):
            return PageType.CASE_STUDIES.value
        if any(seg in path for seg in ["blog", "article", "post", "news"]):
            return PageType.BLOG.value
        return PageType.OTHER.value

    @classmethod
    def analyze_page(
        cls,
        url: str,
        html_content: str,
        visible_text: Optional[str] = None,
        links: Optional[List[str]] = None,
        status_code: int = 200,
    ) -> PageAnalysisResult:
        page_type = cls.classify_page_type(url)
        clean_text = sanitize_untrusted_page_content(visible_text or html_content)
        content_lower = (html_content + " " + clean_text).lower()

        # Extract title
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else None

        # Conversion / Contact flags
        cta_regex = re.compile(
            r"(get in touch|contact us|book a call|schedule a call|free trial|buy now|order now|shop now|add to cart|checkout|sign up|start now)",
            re.IGNORECASE,
        )
        has_cta = bool(cta_regex.search(clean_text) or re.search(r"<button[^>]*>.*?(get|buy|order|book|contact|start)", html_content, re.IGNORECASE))
        has_contact_form = bool(re.search(r"<form[^>]*>.*?(input|textarea).*?</form>", html_content, re.IGNORECASE | re.DOTALL))
        has_phone = bool(re.search(r"(\+?[0-9]{1,3}[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}", clean_text))
        has_email = bool(re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", clean_text))
        has_pricing = bool(re.search(r"(\$\s*[0-9]+|€\s*[0-9]+|£\s*[0-9]+|pricing|per month|/mo\b)", clean_text, re.IGNORECASE))

        # E-commerce detection flags
        has_product_catalog = bool(re.search(r"(products|shop all|add to bag|add to cart|in stock|sku:)", clean_text, re.IGNORECASE))
        has_checkout = bool(re.search(r"(proceed to checkout|shopping cart|view cart|checkout now|stripe|paypal)", clean_text, re.IGNORECASE))

        # Social proof / trust flags
        has_testimonials = bool(re.search(r"(testimonial|client reviews|what our clients say|what people say)", clean_text, re.IGNORECASE))
        has_reviews = bool(re.search(r"(reviews|rated [0-9]|stars?\b|trustpilot)", clean_text, re.IGNORECASE))
        has_social_proof = has_testimonials or has_reviews

        # Observations & Evidence lists
        mobile_obs: List[str] = []
        ux_obs: List[str] = []
        seo_obs: List[str] = []
        perf_obs: List[str] = []
        conv_obs: List[str] = []
        evidence: List[ResearchEvidence] = []

        # 1. SEO observations
        if title:
            if len(title) < 10:
                seo_obs.append(f"Title tag is very short ({len(title)} chars): '{title}'.")
                evidence.append(ResearchEvidence(
                    category=EvidenceCategory.SEO.value,
                    statement=f"Page title is excessively brief: '{title}'",
                    source_url=url,
                    source_type="META_TAG",
                    confidence=0.92,
                ))
            elif len(title) > 70:
                seo_obs.append(f"Title tag is long ({len(title)} chars): '{title}'.")
            else:
                seo_obs.append(f"Optimal title tag detected: '{title}'.")
        else:
            seo_obs.append("Missing <title> tag on page.")
            evidence.append(ResearchEvidence(
                category=EvidenceCategory.SEO.value,
                statement="Page is missing a title tag",
                source_url=url,
                source_type="DOM_OBSERVATION",
                confidence=0.98,
            ))

        meta_desc_match = re.search(r"<meta\s+name=[\"']description[\"']\s+content=[\"']([^\"']*)[\"']", html_content, re.IGNORECASE)
        if not meta_desc_match:
            seo_obs.append("Missing meta description.")
            evidence.append(ResearchEvidence(
                category=EvidenceCategory.SEO.value,
                statement="Page is missing meta description tag",
                source_url=url,
                source_type="DOM_OBSERVATION",
                confidence=0.95,
            ))
        else:
            seo_obs.append(f"Meta description present ({len(meta_desc_match.group(1))} chars).")

        h1_matches = re.findall(r"<h1[^>]*>(.*?)</h1>", html_content, re.IGNORECASE | re.DOTALL)
        if not h1_matches:
            seo_obs.append("Missing H1 heading on page.")
            evidence.append(ResearchEvidence(
                category=EvidenceCategory.SEO.value,
                statement="Page has no H1 heading structure",
                source_url=url,
                source_type="DOM_OBSERVATION",
                confidence=0.95,
            ))
        elif len(h1_matches) > 1:
            seo_obs.append(f"Multiple ({len(h1_matches)}) H1 headings detected.")

        # 2. Mobile observations
        viewport_match = re.search(r"<meta\s+name=[\"']viewport[\"']", html_content, re.IGNORECASE)
        if not viewport_match:
            mobile_obs.append("Missing viewport meta tag, page is not mobile responsive.")
            evidence.append(ResearchEvidence(
                category=EvidenceCategory.MOBILE.value,
                statement="Missing viewport meta tag causing poor mobile rendering",
                source_url=url,
                source_type="DOM_OBSERVATION",
                confidence=0.99,
            ))
        else:
            mobile_obs.append("Viewport meta tag is properly configured for mobile devices.")

        if "overflow-x: scroll" in content_lower or "width: 1200px" in content_lower:
            mobile_obs.append("Horizontal overflow or fixed pixel widths observed.")
            evidence.append(ResearchEvidence(
                category=EvidenceCategory.MOBILE.value,
                statement="Fixed desktop pixel styling creates horizontal scrolling on mobile",
                source_url=url,
                source_type="DOM_OBSERVATION",
                confidence=0.88,
            ))

        # 3. Conversion observations
        if not has_cta:
            conv_obs.append("No clear call-to-action (CTA) button or prompt found on page.")
            evidence.append(ResearchEvidence(
                category=EvidenceCategory.CONVERSION.value,
                statement="Page contains no obvious call-to-action button or conversion pathway",
                source_url=url,
                source_type="PAGE_OBSERVATION",
                confidence=0.92,
            ))
        else:
            conv_obs.append("Clear call-to-action button detected.")

        if not (has_contact_form or has_email or has_phone):
            conv_obs.append("No direct contact mechanism (form, email, or phone) observed.")
            evidence.append(ResearchEvidence(
                category=EvidenceCategory.CONVERSION.value,
                statement="Lack of accessible direct contact information for inquiries",
                source_url=url,
                source_type="PAGE_OBSERVATION",
                confidence=0.90,
            ))

        if not has_social_proof and page_type in (PageType.HOMEPAGE.value, PageType.SERVICES.value):
            conv_obs.append("No testimonials, case studies, or review proof detected.")
            evidence.append(ResearchEvidence(
                category=EvidenceCategory.CONVERSION.value,
                statement="Absence of testimonials or social proof weakens customer trust",
                source_url=url,
                source_type="PAGE_OBSERVATION",
                confidence=0.85,
            ))

        # 4. Performance observations
        scripts_count = len(re.findall(r"<script", html_content, re.IGNORECASE))
        if scripts_count > 25:
            perf_obs.append(f"Heavy script payload with {scripts_count} script tags.")
            evidence.append(ResearchEvidence(
                category=EvidenceCategory.PERFORMANCE.value,
                statement=f"High third-party script count ({scripts_count} tags) slows initial load",
                source_url=url,
                source_type="DOM_OBSERVATION",
                confidence=0.89,
            ))
        else:
            perf_obs.append(f"Moderate script count ({scripts_count} script tags).")

        # 5. UX observations
        nav_match = re.search(r"<(nav|header)[^>]*>", html_content, re.IGNORECASE)
        if not nav_match and page_type == PageType.HOMEPAGE.value:
            ux_obs.append("No standard <nav> or <header> navigation landmark found.")
            evidence.append(ResearchEvidence(
                category=EvidenceCategory.UX.value,
                statement="Missing navigation bar or header element creates user friction",
                source_url=url,
                source_type="DOM_OBSERVATION",
                confidence=0.90,
            ))
        else:
            ux_obs.append("Navigation container detected.")

        # Summary snippet
        summary_text = clean_text[:300].strip().replace("\n", " ") if clean_text else None

        return PageAnalysisResult(
            url=url,
            page_type=page_type,
            title=title,
            status_code=status_code,
            content_summary=summary_text,
            visible_text=clean_text[:5000],
            links_count=len(links or []),
            has_cta=has_cta,
            has_contact_form=has_contact_form,
            has_phone=has_phone,
            has_email=has_email,
            has_pricing=has_pricing,
            has_product_catalog=has_product_catalog,
            has_checkout=has_checkout,
            has_social_proof=has_social_proof,
            has_testimonials=has_testimonials,
            has_reviews=has_reviews,
            mobile_observations=mobile_obs,
            ux_observations=ux_obs,
            seo_observations=seo_obs,
            performance_observations=perf_obs,
            conversion_observations=conv_obs,
            evidence=evidence,
        )
