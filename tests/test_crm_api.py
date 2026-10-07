import uuid
import pytest
from httpx import AsyncClient

ORG_A = "00000000-0000-0000-0000-000000000001"
ORG_B = "00000000-0000-0000-0000-000000000002"


@pytest.mark.asyncio
async def test_company_lifecycle_and_deduplication(client: AsyncClient):
    headers = {"X-Organization-ID": ORG_A}

    # 1. Create company
    payload = {
        "organization_id": ORG_A,
        "name": "TechVerse AI, LLC",
        "domain": "techverse.ai",
        "website_url": "https://techverse.ai",
        "industry": "Artificial Intelligence",
    }
    res = await client.post("/api/v1/companies", json=payload, headers=headers)
    assert res.status_code == 201
    created = res.json()
    assert created["normalized_name"] == "techverse ai"
    assert created["normalized_domain"] == "techverse.ai"

    # 2. Duplicate detection on matching domain
    dup_payload = {
        "organization_id": ORG_A,
        "name": "Different Name",
        "website_url": "http://www.techverse.ai/about",
    }
    dup_res = await client.post("/api/v1/companies", json=dup_payload, headers=headers)
    assert dup_res.status_code == 409

    # 3. List companies with search
    list_res = await client.get("/api/v1/companies?search=techverse", headers=headers)
    assert list_res.status_code == 200
    data = list_res.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == created["id"]


@pytest.mark.asyncio
async def test_contact_lifecycle(client: AsyncClient):
    headers = {"X-Organization-ID": ORG_A}

    payload = {
        "organization_id": ORG_A,
        "first_name": "Sahil",
        "last_name": "Engineer",
        "email": "sahil@techverse.ai",
        "instagram_username": "@sahil_dev",
        "phone": "+1 (555) 019-2834",
    }
    res = await client.post("/api/v1/contacts", json=payload, headers=headers)
    assert res.status_code == 201
    contact = res.json()
    assert contact["email"] == "sahil@techverse.ai"
    assert contact["instagram_username"] == "sahil_dev"
    assert contact["phone"] == "+15550192834"


@pytest.mark.asyncio
async def test_lead_pipeline_and_signals(client: AsyncClient):
    headers = {"X-Organization-ID": ORG_A}

    # 1. Create Lead
    lead_payload = {
        "organization_id": ORG_A,
        "title": "Founder Seeking High Performance Website",
        "summary": "Posted on Reddit looking for Next.js/FastAPI development agency.",
        "lead_type": "FOUNDER",
        "status": "NEW",
        "profile_url": "https://reddit.com/user/startup_founder",
        "intent_score": 85,
        "qualification_score": 90,
        "overall_score": 88,
        "recommended_service": "Premium Website",
    }
    res = await client.post("/api/v1/leads", json=lead_payload, headers=headers)
    assert res.status_code == 201
    lead = res.json()
    lead_id = lead["id"]
    assert lead["status"] == "NEW"

    # 2. Add Buying Signal
    signal_payload = {
        "lead_id": lead_id,
        "signal_type": "WEBSITE_REQUEST",
        "confidence": 0.95,
        "evidence": "Founder explicitly posted: 'Looking to hire agency to redesign website'",
        "source_url": "https://reddit.com/r/startups/comments/12345",
    }
    sig_res = await client.post(f"/api/v1/leads/{lead_id}/signals", json=signal_payload, headers=headers)
    assert sig_res.status_code == 201
    sig_data = sig_res.json()
    assert sig_data["signal_type"] == "WEBSITE_REQUEST"

    # Read Signals
    signals_list = await client.get(f"/api/v1/leads/{lead_id}/signals", headers=headers)
    assert signals_list.status_code == 200
    assert len(signals_list.json()) == 1

    # 3. Invalid Status Transition: NEW -> WON (must fail)
    invalid_trans = {
        "new_status": "WON",
        "reason": "Direct close attempted",
    }
    inv_res = await client.post(f"/api/v1/leads/{lead_id}/status", json=invalid_trans, headers=headers)
    assert inv_res.status_code == 422

    # 4. Valid Status Transition: NEW -> QUALIFIED
    valid_trans = {
        "new_status": "QUALIFIED",
        "reason": "Verified budget and timeline match",
    }
    val_res = await client.post(f"/api/v1/leads/{lead_id}/status", json=valid_trans, headers=headers)
    assert val_res.status_code == 200
    assert val_res.json()["status"] == "QUALIFIED"

    # 5. Check Pipeline Event History
    history_res = await client.get(f"/api/v1/leads/{lead_id}/pipeline", headers=headers)
    assert history_res.status_code == 200
    history = history_res.json()
    assert len(history) >= 2  # Initial creation event + status transition event


@pytest.mark.asyncio
async def test_multi_tenancy_isolation(client: AsyncClient):
    # Create lead in Organization A
    lead_payload = {
        "organization_id": ORG_A,
        "title": "Org A Private Lead",
        "profile_url": "https://instagram.com/org_a_prospect",
    }
    res = await client.post("/api/v1/leads", json=lead_payload, headers={"X-Organization-ID": ORG_A})
    assert res.status_code == 201
    org_a_lead_id = res.json()["id"]

    # Organization B attempts to view Organization A's lead directly
    sec_res = await client.get(f"/api/v1/leads/{org_a_lead_id}", headers={"X-Organization-ID": ORG_B})
    assert sec_res.status_code == 404

    # Organization B lists leads -> Should receive 0 leads
    list_res = await client.get("/api/v1/leads", headers={"X-Organization-ID": ORG_B})
    assert list_res.status_code == 200
    assert list_res.json()["total"] == 0
