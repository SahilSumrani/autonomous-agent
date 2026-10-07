import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from services.api.app.main import app
from services.api.app.core.database import AsyncSessionLocal
from services.api.app.models.agent import AgentSession
from services.api.app.models.crm import Organization


async def verify_live_pairing():
    # Use lifespan to simulate real server startup
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client:
            # 1. Challenge without header
            res_ch = await client.post("/api/v1/agent/browser/challenge")
            print("Challenge response:", res_ch.status_code, res_ch.json())
            assert res_ch.status_code == 200
            code = res_ch.json()["pairing_code"]

            # 2. Pair without header
            pair_payload = {
                "pairing_code": code,
                "browser_id": "chrome-ext-live-test-001",
                "client_version": "2.0.0",
            }
            res_pair = await client.post("/api/v1/agent/browser/pair", json=pair_payload)
            print("Pair response:", res_pair.status_code, res_pair.json())
            assert res_pair.status_code == 200
            pair_data = res_pair.json()
            session_id = uuid.UUID(pair_data["session_id"])

            # 3. Status check
            res_status = await client.get(f"/api/v1/agent/browser/status?session_id={session_id}")
            print("Status check response:", res_status.status_code, res_status.json())
            assert res_status.status_code == 200

            # 4. Verify in real PostgreSQL database
            async with AsyncSessionLocal() as db:
                stmt = select(AgentSession).where(AgentSession.id == session_id)
                sess = (await db.execute(stmt)).scalar_one_or_none()
                print("Database record in PostgreSQL:", sess.id, sess.organization_id, sess.browser_id, sess.status)
                assert sess is not None
                assert str(sess.organization_id) == "00000000-0000-0000-0000-000000000001"

    print("ALL LIVE VERIFICATION STEPS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(verify_live_pairing())
