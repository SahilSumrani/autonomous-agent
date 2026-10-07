import pytest
from services.api.app.services.normalization import (
    normalize_company_name,
    normalize_domain,
    normalize_email,
    normalize_phone,
    normalize_profile_url,
    normalize_username,
)


def test_normalize_domain_canonical_forms():
    assert normalize_domain("https://www.example.com/") == "example.com"
    assert normalize_domain("http://example.com") == "example.com"
    assert normalize_domain("www.example.com") == "example.com"
    assert normalize_domain("example.com/") == "example.com"
    assert normalize_domain("WWW.EXAMPLE.COM") == "example.com"
    assert normalize_domain("https://example.com:8080/path?key=val#hash") == "example.com"


def test_normalize_domain_subdomains_preserved():
    assert normalize_domain("https://app.example.com/login") == "app.example.com"
    assert normalize_domain("http://shop.brand.co.uk/") == "shop.brand.co.uk"
    assert normalize_domain("www.blog.techverse.ai") == "blog.techverse.ai"


def test_normalize_domain_edge_cases():
    assert normalize_domain(None) is None
    assert normalize_domain("") is None
    assert normalize_domain("   ") is None


def test_normalize_email():
    assert normalize_email("  SAHIL@TECHVERSE.AI ") == "sahil@techverse.ai"
    assert normalize_email("Test.User+Filter@Domain.com") == "test.user+filter@domain.com"
    assert normalize_email("invalid-email") is None
    assert normalize_email("@missinglocal.com") is None
    assert normalize_email("missingdomain@") is None
    assert normalize_email(None) is None


def test_normalize_company_name():
    assert normalize_company_name("  TechVerse   AI,  LLC  ") == "techverse ai"
    assert normalize_company_name("Acme Corporation") == "acme"
    assert normalize_company_name("Global Logistics Inc.") == "global logistics"
    assert normalize_company_name("Stripe, Inc.") == "stripe"
    # Verify non-identical names are distinguishable
    assert normalize_company_name("ABC Technologies") == "abc technologies"
    assert normalize_company_name("ABC Technology") == "abc technology"
    assert normalize_company_name("ABC Technologies") != normalize_company_name("ABC Technology")
    assert normalize_company_name(None) is None


def test_normalize_profile_url():
    # Tracking parameters stripped, trailing slash removed, https enforced
    raw = "http://www.instagram.com/techverse_ai/?igsh=abc123xyz&utm_source=feed"
    expected = "https://instagram.com/techverse_ai"
    assert normalize_profile_url(raw) == expected

    linkedin = "https://www.linkedin.com/in/sahil-dev/?utm_campaign=share"
    assert normalize_profile_url(linkedin) == "https://linkedin.com/in/sahil-dev"
    assert normalize_profile_url(None) is None


def test_normalize_username():
    assert normalize_username("@SahilDev") == "sahildev"
    assert normalize_username("@@techverse_ai") == "techverse_ai"
    assert normalize_username("  user_name  ") == "user_name"
    assert normalize_username(None) is None


def test_normalize_phone():
    assert normalize_phone("+1 (555) 123-4567") == "+15551234567"
    assert normalize_phone("  +91 98765 43210  ") == "+919876543210"
    assert normalize_phone("(555) 123-4567") == "5551234567"
    assert normalize_phone(None) is None
