import re
from typing import Dict, List, Optional
from services.api.app.agents.research.research_models import TechnologyFinding


TECH_SIGNATURES = {
    # CMS / Site Builders
    "WordPress": {
        "category": "CMS",
        "patterns": [
            r"wp-content",
            r"wp-includes",
            r"<meta\s+name=[\"']generator[\"']\s+content=[\"']WordPress",
            r"/wp-json/",
        ],
        "confidence": 0.95,
        "evidence": "HTML references WordPress core directories (wp-content/wp-includes) or meta generator."
    },
    "Shopify": {
        "category": "ECOMMERCE",
        "patterns": [
            r"cdn\.shopify\.com",
            r"Shopify\.theme",
            r"shopify-section",
            r"myshopify\.com",
            r"window\.Shopify",
        ],
        "confidence": 0.98,
        "evidence": "Assets served from cdn.shopify.com and Shopify theme DOM objects detected."
    },
    "WooCommerce": {
        "category": "ECOMMERCE",
        "patterns": [
            r"woocommerce",
            r"wc-block",
            r"wc-ajax",
            r"woocommerce-Price-amount",
        ],
        "confidence": 0.95,
        "evidence": "WooCommerce CSS classes, scripts, or REST endpoints detected."
    },
    "Magento": {
        "category": "ECOMMERCE",
        "patterns": [
            r"mage/cookies",
            r"Mage\.Cookies",
            r"/static/frontend/Magento",
            r"varien/js",
        ],
        "confidence": 0.95,
        "evidence": "Magento static assets and frontend scripts detected."
    },
    "Webflow": {
        "category": "CMS",
        "patterns": [
            r"webflow\.com",
            r"wf-page",
            r"wf-site",
            r"assets\.website-files\.com",
            r"data-wf-page",
        ],
        "confidence": 0.98,
        "evidence": "Webflow data attributes and hosting asset patterns detected."
    },
    "Wix": {
        "category": "CMS",
        "patterns": [
            r"wix\.com",
            r"wix-warmup-data",
            r"static\.wixstatic\.com",
            r"_wix_browser_sess",
        ],
        "confidence": 0.95,
        "evidence": "Wix CDN assets and static runtime scripts detected."
    },
    "Squarespace": {
        "category": "CMS",
        "patterns": [
            r"squarespace\.com",
            r"static\.squarespace\.com",
            r"squarespace-headers",
        ],
        "confidence": 0.95,
        "evidence": "Squarespace CDN scripts and header markers detected."
    },

    # Frontend Frameworks
    "Next.js": {
        "category": "FRONTEND",
        "patterns": [
            r"/_next/static",
            r"__NEXT_DATA__",
            r"next-head",
        ],
        "confidence": 0.98,
        "evidence": "Next.js asset paths (/_next/static) and __NEXT_DATA__ state container detected."
    },
    "React": {
        "category": "FRONTEND",
        "patterns": [
            r"react\.production\.min\.js",
            r"data-reactroot",
            r"_reactRootContainer",
            r"react-dom",
        ],
        "confidence": 0.90,
        "evidence": "React DOM root markers or runtime script references detected."
    },
    "Nuxt": {
        "category": "FRONTEND",
        "patterns": [
            r"/_nuxt/",
            r"__NUXT__",
        ],
        "confidence": 0.98,
        "evidence": "Nuxt.js build output directory (/_nuxt/) and state window object detected."
    },
    "Vue": {
        "category": "FRONTEND",
        "patterns": [
            r"vue\.min\.js",
            r"data-v-[a-f0-9]{8}",
            r"__VUE__",
        ],
        "confidence": 0.90,
        "evidence": "Vue.js scoped CSS attributes or runtime references detected."
    },
    "Angular": {
        "category": "FRONTEND",
        "patterns": [
            r"ng-version",
            r"angular\.min\.js",
            r"ng-star-inserted",
        ],
        "confidence": 0.92,
        "evidence": "Angular root directives and runtime tags detected."
    },
    "Svelte": {
        "category": "FRONTEND",
        "patterns": [
            r"svelte-[a-z0-9]{6}",
            r"/_app/immutable/",
        ],
        "confidence": 0.90,
        "evidence": "Svelte component class hashes and SvelteKit immutable bundle paths detected."
    },

    # Backend / Stacks
    "PHP": {
        "category": "BACKEND",
        "patterns": [
            r"\.php(\?|$)",
            r"X-Powered-By:\s*PHP",
            r"PHPSESSID",
        ],
        "confidence": 0.92,
        "evidence": "PHP session cookies, file extensions, or response headers detected."
    },
    "Laravel": {
        "category": "BACKEND",
        "patterns": [
            r"laravel_session",
            r"XSRF-TOKEN.*laravel",
        ],
        "confidence": 0.90,
        "evidence": "Laravel session cookies and token structures detected."
    },
    "Django": {
        "category": "BACKEND",
        "patterns": [
            r"csrftoken",
            r"__admin__",
            r"django",
        ],
        "confidence": 0.85,
        "evidence": "Django CSRF cookie patterns and asset naming detected."
    },
    "Rails": {
        "category": "BACKEND",
        "patterns": [
            r"csrf-param[\"']\s+content=[\"']authenticity_token",
            r"_rails_session",
        ],
        "confidence": 0.90,
        "evidence": "Ruby on Rails authenticity_token CSRF meta tags detected."
    },
    "Node.js": {
        "category": "BACKEND",
        "patterns": [
            r"express:sess",
            r"connect\.sid",
        ],
        "confidence": 0.85,
        "evidence": "Express/Connect session cookie signatures detected."
    },

    # Analytics / Tracking
    "Google Analytics": {
        "category": "ANALYTICS",
        "patterns": [
            r"google-analytics\.com/(analytics|gtag)",
            r"UA-[0-9]+-[0-9]+",
            r"G-[A-Z0-9]{8,12}",
        ],
        "confidence": 0.95,
        "evidence": "Google Analytics tracking IDs and gtag script sources detected."
    },
    "Google Tag Manager": {
        "category": "ANALYTICS",
        "patterns": [
            r"googletagmanager\.com/gtm\.js",
            r"GTM-[A-Z0-9]+",
        ],
        "confidence": 0.95,
        "evidence": "Google Tag Manager container container script detected."
    },
    "Meta Pixel": {
        "category": "ANALYTICS",
        "patterns": [
            r"connect\.facebook\.net/[a-zA-Z_]+/fbevents\.js",
            r"fbq\(['\"]init",
        ],
        "confidence": 0.95,
        "evidence": "Meta/Facebook Pixel tracking script detected."
    },
    "Hotjar": {
        "category": "ANALYTICS",
        "patterns": [
            r"static\.hotjar\.com/c/hotjar-",
            r"_hjSettings",
        ],
        "confidence": 0.95,
        "evidence": "Hotjar tracking snippet and settings object detected."
    },
    "Microsoft Clarity": {
        "category": "ANALYTICS",
        "patterns": [
            r"www\.clarity\.ms/tag/",
            r"clarity\(['\"]set",
        ],
        "confidence": 0.95,
        "evidence": "Microsoft Clarity script tags detected."
    },

    # Infrastructure / CDN
    "Cloudflare": {
        "category": "CDN_INFRASTRUCTURE",
        "patterns": [
            r"cloudflare",
            r"cdnjs\.cloudflare\.com",
            r"__cf_bm",
            r"cf-ray",
        ],
        "confidence": 0.92,
        "evidence": "Cloudflare CDN markers and caching cookies detected."
    },
    "Vercel": {
        "category": "CDN_INFRASTRUCTURE",
        "patterns": [
            r"vercel\.app",
            r"x-vercel-id",
            r"_vercel",
        ],
        "confidence": 0.95,
        "evidence": "Vercel deployment headers or routing tokens detected."
    },
    "Netlify": {
        "category": "CDN_INFRASTRUCTURE",
        "patterns": [
            r"netlify\.app",
            r"x-nf-request-id",
        ],
        "confidence": 0.95,
        "evidence": "Netlify routing indicators and asset hosts detected."
    },
    "AWS": {
        "category": "CDN_INFRASTRUCTURE",
        "patterns": [
            r"amazonaws\.com",
            r"cloudfront\.net",
        ],
        "confidence": 0.92,
        "evidence": "AWS S3 / CloudFront asset endpoints detected."
    },
}


class TechnologyDetector:
    """Detects technology stacks, CMS, frameworks, and analytics from observable HTML/scripts."""

    @classmethod
    def detect_technologies(
        cls,
        html_content: str,
        scripts: Optional[List[str]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> List[TechnologyFinding]:
        findings: List[TechnologyFinding] = []
        combined_text = html_content or ""
        if scripts:
            combined_text += "\n" + "\n".join(scripts)
        if headers:
            combined_text += "\n" + "\n".join(f"{k}: {v}" for k, v in headers.items())

        for tech_name, spec in TECH_SIGNATURES.items():
            for pattern in spec["patterns"]:
                if re.search(pattern, combined_text, re.IGNORECASE):
                    findings.append(
                        TechnologyFinding(
                            technology=tech_name,
                            category=spec["category"],
                            confidence=spec["confidence"],
                            evidence=spec["evidence"],
                        )
                    )
                    break  # Found one pattern match for this tech, move to next

        return findings
