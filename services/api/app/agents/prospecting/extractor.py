import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from services.api.app.services.normalization import (
    is_disallowed_business_domain,
    is_platform_owned_domain,
    normalize_company_name,
    normalize_domain,
    normalize_email,
    normalize_phone,
    normalize_username,
)

# Email regex matching RFC 5322 simplified pattern
EMAIL_REGEX = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"
)

# Common placeholder/bogus emails to discard
PLACEHOLDER_EMAIL_DOMAINS = {
    "example.com",
    "domain.com",
    "test.com",
    "email.com",
    "yoursite.com",
    "mysite.com",
}

# Phone regex (international & US formats)
PHONE_REGEX = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,5}"
)

# Industry/category keyword detection
CATEGORY_PATTERNS = [
    (r"\b(e-?commerce|online store|boutique|shop|apparel|clothing brand|jewelry)\b", "E-commerce & Retail"),
    (r"\b(saas|software|platform|cloud|api|dev tools|fintech)\b", "Software & SaaS"),
    (r"\b(agency|consulting|marketing|ad agency|creative studio)\b", "Agency & Consulting"),
    (r"\b(restaurant|cafe|bakery|bar|catering|food & beverage)\b", "Food & Hospitality"),
    (r"\b(real estate|realty|property|brokerage|realtor)\b", "Real Estate"),
    (r"\b(clinic|dental|doctor|healthcare|wellness|fitness|gym)\b", "Health & Wellness"),
    (r"\b(construction|plumbing|electrician|contractor|hvac|roofing)\b", "Home & Commercial Services"),
    (r"\b(law firm|legal|attorney|accounting|cpa|bookkeeping)\b", "Professional Services"),
]


class ExtractedBusinessInfo(BaseModel):
    """Normalized business profile extracted without hallucination."""
    company_name: Optional[str] = None
    domain: Optional[str] = None
    social_handle: Optional[str] = None
    business_category: Optional[str] = None
    description: Optional[str] = None
    public_email: Optional[str] = None
    public_phone: Optional[str] = None
    location: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: List[str] = Field(default_factory=list)


class BusinessExtractor:
    """
    Extracts truthful, evidence-backed business entity metadata from page observations.
    Never invents or hallucinates details: missing fields remain None.
    """

    @classmethod
    def extract_emails(cls, text: str) -> List[str]:
        if not text:
            return []
        matches = EMAIL_REGEX.findall(text)
        valid = []
        for em in matches:
            norm = normalize_email(em)
            if not norm:
                continue
            # Filter dummy emails and image extensions
            parts = norm.split("@")
            if len(parts) == 2:
                dom = parts[1].lower()
                if dom not in PLACEHOLDER_EMAIL_DOMAINS and not any(ext in dom for ext in [".png", ".jpg", ".webp"]):
                    if norm not in valid:
                        valid.append(norm)
        return valid

    @classmethod
    def extract_phone(cls, text: str) -> Optional[str]:
        if not text:
            return None
        matches = PHONE_REGEX.findall(text)
        for m in matches:
            clean = re.sub(r"[^\d+]", "", m)
            if 7 <= len(clean) <= 15:
                return normalize_phone(m)
        return None

    @classmethod
    def detect_category(cls, text: str) -> Optional[str]:
        if not text:
            return None
        for pattern, cat in CATEGORY_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return cat
        return None

    @classmethod
    def extract_business(
        cls,
        observation: Dict[str, Any],
        profile_url: Optional[str] = None,
        recipient_handle: Optional[str] = None,
    ) -> ExtractedBusinessInfo:
        text = observation.get("visible_text") or ""
        title = observation.get("page_title") or ""
        url = observation.get("url") or ""
        links = observation.get("links") or []

        evidence: List[str] = []
        confidence_points = 0.0

        # 1. Company Name resolution
        company_name = None
        if title:
            # Clean common SEO suffixes
            clean_title = re.sub(r"[-|•].*$", "", title).strip()
            # Clean common platform tails
            clean_title = clean_title.replace("• Instagram photos and videos", "").strip()
            clean_title = clean_title.replace("- Reddit", "").strip()
            if clean_title and len(clean_title) <= 70 and not clean_title.lower().startswith("http"):
                company_name = normalize_company_name(clean_title)
                evidence.append(f"Derived company name from page title: '{company_name}'")
                confidence_points += 0.3

        # 2. Domain resolution
        domain = None
        # Check current URL if not a social platform, email provider or placeholder
        url_domain = normalize_domain(url)
        if url_domain and not is_disallowed_business_domain(url_domain):
            domain = url_domain
            evidence.append(f"Extracted company domain directly from URL: '{domain}'")
            confidence_points += 0.4
        else:
            # Check links for external business domains
            for link in links:
                if isinstance(link, str):
                    ld = normalize_domain(link)
                    if ld and not is_disallowed_business_domain(ld):
                        domain = ld
                        evidence.append(f"Extracted website domain from link: '{domain}'")
                        confidence_points += 0.3
                        break

        # If company name is still missing and domain exists
        if not company_name and domain:
            company_name = domain.split(".")[0].capitalize()
            evidence.append(f"Inferred company name from domain: '{company_name}'")
            confidence_points += 0.2

        # 3. Handle resolution
        handle = recipient_handle
        if not handle and profile_url:
            handle = normalize_username(profile_url)
        if handle:
            evidence.append(f"Identified social handle: '{handle}'")
            confidence_points += 0.1

        # 4. Category
        category = cls.detect_category(f"{title} {text[:1500]}")
        if category:
            evidence.append(f"Classified business category: '{category}'")
            confidence_points += 0.1

        # 5. Public contact info
        emails = cls.extract_emails(text)
        public_email = emails[0] if emails else None
        if public_email:
            evidence.append(f"Found public contact email: '{public_email}'")
            confidence_points += 0.1

        public_phone = cls.extract_phone(text)
        if public_phone:
            evidence.append(f"Found public contact phone: '{public_phone}'")

        # 6. Description
        description = None
        meta_desc = observation.get("meta_description")
        if meta_desc and len(meta_desc.strip()) > 10:
            description = meta_desc.strip()[:500]
        elif text:
            # First 200 clean characters
            first_lines = " ".join([l.strip() for l in text.split("\n") if len(l.strip()) > 20][:2])
            description = first_lines[:300] if first_lines else None

        final_conf = min(1.0, max(0.1, confidence_points))

        return ExtractedBusinessInfo(
            company_name=company_name,
            domain=domain,
            social_handle=handle,
            business_category=category,
            description=description,
            public_email=public_email,
            public_phone=public_phone,
            confidence=round(final_conf, 2),
            evidence=evidence,
        )
