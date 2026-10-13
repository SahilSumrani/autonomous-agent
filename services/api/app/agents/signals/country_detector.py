import re
from typing import Optional, Tuple
from pydantic import BaseModel, Field


class CountryEvidence(BaseModel):
    country: Optional[str] = None  # "INDIA" | "USA" | None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: Optional[str] = None
    city_or_state: Optional[str] = None


INDIA_CITIES = {
    "delhi", "new delhi", "mumbai", "bombay", "bengaluru", "bangalore", "hyderabad",
    "chennai", "madras", "kolkata", "calcutta", "pune", "ahmedabad", "jaipur",
    "surat", "lucknow", "kanpur", "nagpur", "indore", "thane", "bhopal",
    "visakhapatnam", "patna", "vadodara", "ghaziabad", "ludhiana", "agra",
    "nashik", "faridabad", "meerut", "rajkot", "varanasi", "srinagar",
    "aurangabad", "amritsar", "navi mumbai", "prayagraj", "allahabad",
    "coimbatore", "vijayawada", "jodhpur", "madurai", "raipur", "chandigarh",
    "guwahati", "mysore", "gurgaon", "gurugram", "noida", "jalandhar",
    "bhubaneswar", "salem", "warangal", "guntur", "kochi", "cochin",
    "dehradun", "ranchi", "kerala", "karnataka", "maharashtra", "gujarat",
    "tamil nadu", "punjab", "haryana", "rajasthan", "uttar pradesh", "telangana",
}

USA_STATES_AND_CITIES = {
    "california", "texas", "florida", "new york", "pennsylvania", "illinois",
    "ohio", "georgia", "north carolina", "michigan", "new jersey", "virginia",
    "washington", "arizona", "massachusetts", "tennessee", "indiana", "missouri",
    "maryland", "wisconsin", "colorado", "minnesota", "south carolina", "alabama",
    "louisiana", "kentucky", "oregon", "oklahoma", "connecticut", "utah",
    "iowa", "nevada", "arkansas", "mississippi", "kansas", "new mexico",
    "nebraska", "idaho", "west virginia", "hawaii", "new hampshire", "maine",
    "montana", "rhode island", "delaware", "south dakota", "north dakota",
    "alaska", "vermont", "wyoming",
    # Cities
    "los angeles", "chicago", "houston", "phoenix", "philadelphia", "san antonio",
    "san diego", "dallas", "austin", "san jose", "fort worth", "columbus",
    "charlotte", "indianapolis", "san francisco", "seattle", "denver",
    "washington dc", "boston", "las vegas", "portland", "detroit", "louisville",
    "baltimore", "milwaukee", "albuquerque", "tucson", "fresno", "sacramento",
    "atlanta", "kansas city", "miami", "raleigh", "omaha", "long beach",
    "virginia beach", "oakland", "minneapolis", "tampa", "arlington",
}


class CountryDetectionEngine:
    """
    Deterministic country detection engine evaluating India and USA geographic evidence.
    Enforces truthfulness: never fabricates country when evidence is absent.
    """

    @classmethod
    def evaluate(
        cls,
        text: Optional[str] = None,
        domain: Optional[str] = None,
        source_url: Optional[str] = None,
        declared_location: Optional[str] = None,
    ) -> CountryEvidence:
        combined_text = " ".join(filter(None, [declared_location, text, domain, source_url])).lower()

        if not combined_text:
            return CountryEvidence(country=None, confidence=0.0, evidence=None)

        # 1. Domain TLD Check
        if domain:
            dom_lower = domain.lower()
            if dom_lower.endswith(".in") or ".co.in" in dom_lower:
                return CountryEvidence(
                    country="INDIA",
                    confidence=0.98,
                    evidence=f"Indian domain TLD detected: {domain}",
                )
            if dom_lower.endswith(".us") or dom_lower.endswith(".gov") or dom_lower.endswith(".mil"):
                return CountryEvidence(
                    country="USA",
                    confidence=0.95,
                    evidence=f"United States domain TLD detected: {domain}",
                )

        # 2. Phone prefix check
        if re.search(r"(?:\+91[\s\-]?[6-9]\d{9}|(?:^|\s)0[6-9]\d{9})", combined_text):
            return CountryEvidence(
                country="INDIA",
                confidence=0.96,
                evidence="Verified Indian phone format (+91) detected.",
            )
        if re.search(r"(?:\+1[\s\-]?[2-9]\d{2}[\s\-]?\d{3}[\s\-]?\d{4}|\([2-9]\d{2}\)\s*\d{3}[\s\-]?\d{4})", combined_text):
            return CountryEvidence(
                country="USA",
                confidence=0.90,
                evidence="Verified North American phone format (+1) detected.",
            )

        # 3. Currency symbols
        has_inr = bool(re.search(r"(?:₹|inr|rs\.?|rupees?)\s*\d+", combined_text, re.IGNORECASE))
        has_usd = bool(re.search(r"(?:usd|\$\s*\d+)", combined_text, re.IGNORECASE))

        # 4. Explicit Country Mentions
        india_explicit = bool(re.search(r"\b(india|indian|bharat)\b", combined_text, re.IGNORECASE))
        usa_explicit = bool(re.search(r"\b(united states|usa|u\.s\.a|u\.s\.|america)\b", combined_text, re.IGNORECASE))

        # 5. City/State Mentions
        matched_india_city = next((city for city in INDIA_CITIES if re.search(rf"\b{re.escape(city)}\b", combined_text)), None)
        matched_usa_city = next((city for city in USA_STATES_AND_CITIES if re.search(rf"\b{re.escape(city)}\b", combined_text)), None)

        if india_explicit or matched_india_city or has_inr:
            evidence_parts = []
            if matched_india_city:
                evidence_parts.append(f"City/Region: '{matched_india_city.title()}'")
            if india_explicit:
                evidence_parts.append("Explicit mention of India")
            if has_inr:
                evidence_parts.append("Indian currency (₹/INR) referenced")

            conf = 0.92 if (matched_india_city and india_explicit) else (0.85 if matched_india_city else 0.80)
            return CountryEvidence(
                country="INDIA",
                confidence=conf,
                evidence="; ".join(evidence_parts),
                city_or_state=matched_india_city.title() if matched_india_city else None,
            )

        if usa_explicit or (matched_usa_city and (has_usd or usa_explicit or declared_location)):
            evidence_parts = []
            if matched_usa_city:
                evidence_parts.append(f"State/City: '{matched_usa_city.title()}'")
            if usa_explicit:
                evidence_parts.append("Explicit mention of USA/United States")
            if has_usd:
                evidence_parts.append("USD ($) currency referenced")

            conf = 0.90 if (matched_usa_city and usa_explicit) else 0.80
            return CountryEvidence(
                country="USA",
                confidence=conf,
                evidence="; ".join(evidence_parts),
                city_or_state=matched_usa_city.title() if matched_usa_city else None,
            )

        # No conclusive country signal found
        return CountryEvidence(country=None, confidence=0.0, evidence=None)
