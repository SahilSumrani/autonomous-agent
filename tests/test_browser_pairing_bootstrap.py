import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.seeds.dev_seed import (
    DEV_ORGANIZATION_ID,
    DEV_ORGANIZATION_NAME,
    DEV_ORGANIZATION_SLUG,
    seed_development_organization,
)
from packages.config.settings import settings
from packages.shared_types.agent import SessionStatus
from services.api.app.models.agent import AgentSession
from services.api.app.models.crm import Organization

ORG_A = uuid.UUID("00000000-0000-0000-0000-000000000001")
ORG_B = uuid.UUID("00000000-0000-0000-0000-000000000002")


@pytest.mark.asyncio
async def test_development_organization_bootstrap_exists(test_db_session: AsyncSession):
    """Requirement 7.A: Development organization exists with deterministic UUID and row in table."""
    org = await seed_development_organization(test_db_session)
    assert org.id == DEV_ORGANIZATION_ID
    assert org.name in (DEV_ORGANIZATION_NAME, "TechVerse Dev Workspace")
    assert org.slug == DEV_ORGANIZATION_SLUG

    # Verify query directly from DB
    stmt = select(Organization).where(Organization.id == DEV_ORGANIZATION_ID)
    res = await test_db_session.execute(stmt)
    db_org = res.scalar_one_or_none()
    assert db_org is not None
    assert db_org.id == DEV_ORGANIZATION_ID


@pytest.mark.asyncio
async def test_pairing_without_x_organization_id_in_dev(client: AsyncClient, test_db_session: AsyncSession):
    """Requirement 7.B: Pairing without X-Organization-ID in development resolves dev org and creates AgentSession."""
    # Ensure dev org is present
    await seed_development_organization(test_db_session)

    # 1. Challenge without header
    res_ch = await client.post("/api/v1/agent/browser/challenge")
    assert res_ch.status_code == 200
    ch_data = res_ch.json()
    assert "pairing_code" in ch_data
    code = ch_data["pairing_code"]

    # 2. Pair without header
    pair_payload = {
        "pairing_code": code,
        "browser_id": "chrome-ext-dev-test",
        "client_version": "2.0.0",
    }
    res_pair = await client.post("/api/v1/agent/browser/pair", json=pair_payload)
    assert res_pair.status_code == 200
    pair_data = res_pair.json()
    assert pair_data["organization_id"] == str(DEV_ORGANIZATION_ID)
    assert "token" in pair_data

    # 3. Verify AgentSession in DB
    session_id = uuid.UUID(pair_data["session_id"])
    stmt = select(AgentSession).where(AgentSession.id == session_id)
    res_sess = await test_db_session.execute(stmt)
    sess = res_sess.scalar_one_or_none()
    assert sess is not None
    assert sess.organization_id == DEV_ORGANIZATION_ID
    assert sess.browser_id == "chrome-ext-dev-test"
    assert sess.status == SessionStatus.IDLE.value


@pytest.mark.asyncio
async def test_pairing_with_valid_x_organization_id(client: AsyncClient, test_db_session: AsyncSession):
    """Requirement 7.C: Pairing with valid X-Organization-ID belongs to correct organization."""
    headers = {"X-Organization-ID": str(ORG_B)}

    # 1. Challenge with Org B
    res_ch = await client.post("/api/v1/agent/browser/challenge", headers=headers)
    assert res_ch.status_code == 200
    code = res_ch.json()["pairing_code"]

    # 2. Pair
    pair_payload = {
        "pairing_code": code,
        "browser_id": "chrome-ext-org-b",
        "client_version": "2.0.0",
    }
    res_pair = await client.post("/api/v1/agent/browser/pair", json=pair_payload)
    assert res_pair.status_code == 200
    pair_data = res_pair.json()
    assert pair_data["organization_id"] == str(ORG_B)

    # 3. Verify in DB
    session_id = uuid.UUID(pair_data["session_id"])
    stmt = select(AgentSession).where(AgentSession.id == session_id)
    res_sess = await test_db_session.execute(stmt)
    sess = res_sess.scalar_one()
    assert sess.organization_id == ORG_B


@pytest.mark.asyncio
async def test_pairing_with_nonexistent_org_id_fails_cleanly(client: AsyncClient, test_db_session: AsyncSession):
    """Requirement 7.D: Pairing with nonexistent organization ID fails cleanly without 500 and no session created."""
    fake_org_id = uuid.uuid4()
    headers = {"X-Organization-ID": str(fake_org_id)}

    # Challenge with nonexistent org fails cleanly with 404
    res_ch = await client.post("/api/v1/agent/browser/challenge", headers=headers)
    assert res_ch.status_code == 404
    assert "not found" in res_ch.json()["detail"].lower()

    # Ensure no sessions created for fake org
    stmt = select(func.count(AgentSession.id)).where(AgentSession.organization_id == fake_org_id)
    res_count = await test_db_session.execute(stmt)
    assert res_count.scalar() == 0


@pytest.mark.asyncio
async def test_multi_tenant_isolation_prevents_cross_org_access(client: AsyncClient, test_db_session: AsyncSession):
    """Requirement 7.E: Organization A cannot access or control sessions belonging to Organization B."""
    # Create session in Org A
    res_ch = await client.post("/api/v1/agent/browser/challenge", headers={"X-Organization-ID": str(ORG_A)})
    code = res_ch.json()["pairing_code"]
    res_pair = await client.post(
        "/api/v1/agent/browser/pair",
        json={"pairing_code": code, "browser_id": "tenant-iso-browser"},
    )
    session_id = res_pair.json()["session_id"]

    # Org B attempts to inspect Org A's session -> 404
    status_res = await client.get(
        f"/api/v1/agent/browser/status?session_id={session_id}",
        headers={"X-Organization-ID": str(ORG_B)},
    )
    assert status_res.status_code == 404

    # Org B attempts to pause Org A's session -> 404
    pause_res = await client.post(
        "/api/v1/agent/browser/pause",
        json={"session_id": session_id, "reason": "Unauthorized attempt"},
        headers={"X-Organization-ID": str(ORG_B)},
    )
    assert pause_res.status_code == 404


@pytest.mark.asyncio
async def test_repeated_bootstrap_is_idempotent(test_db_session: AsyncSession):
    """Requirement 7.F: Repeated seed/bootstrap does not create duplicate organization records."""
    # Execute bootstrap multiple times
    org1 = await seed_development_organization(test_db_session)
    org2 = await seed_development_organization(test_db_session)
    org3 = await seed_development_organization(test_db_session)

    assert org1.id == org2.id == org3.id == DEV_ORGANIZATION_ID

    # Verify exactly 1 record exists with this ID
    stmt = select(func.count(Organization.id)).where(Organization.id == DEV_ORGANIZATION_ID)
    res = await test_db_session.execute(stmt)
    assert res.scalar() == 1


@pytest.mark.asyncio
async def test_full_phase6_pairing_regression(client: AsyncClient, test_db_session: AsyncSession):
    """Requirement 7.G: Full Phase 6 pairing regression: challenge -> pair -> session creation -> status."""
    await seed_development_organization(test_db_session)

    # 1. Challenge
    ch_res = await client.post("/api/v1/agent/browser/challenge")
    assert ch_res.status_code == 200
    ch_data = ch_res.json()
    code = ch_data["pairing_code"]
    assert code.startswith("TV-")

    # 2. Pair
    pair_res = await client.post(
        "/api/v1/agent/browser/pair",
        json={
            "pairing_code": code,
            "browser_id": "full-regression-chrome-1",
            "client_version": "2.0.0",
        },
    )
    assert pair_res.status_code == 200
    pair_data = pair_res.json()
    assert "token" in pair_data
    session_id = pair_data["session_id"]
    org_id = pair_data["organization_id"]
    assert org_id == str(DEV_ORGANIZATION_ID)

    # 3. Status check
    status_res = await client.get(f"/api/v1/agent/browser/status?session_id={session_id}")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["session_id"] == session_id
    assert status_data["organization_id"] == org_id


@pytest.mark.asyncio
async def test_production_environment_rejects_missing_org_header(client: AsyncClient, monkeypatch):
    """Requirement 4: In production, missing X-Organization-ID is rejected and does NOT fall back to dev org."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    res = await client.post("/api/v1/agent/browser/challenge")
    assert res.status_code == 400
    assert "missing required x-organization-id" in res.json()["detail"].lower()
