import sys
sys.path.insert(0, ".")
import asyncio
from services.api.app.core.database import async_session_factory
from services.api.app.models.prospecting import ProspectingJob, ProspectCandidate, ProspectObservation
from sqlalchemy import select

async def main():
    async with async_session_factory() as session:
        jobs = (await session.execute(select(ProspectingJob).order_by(ProspectingJob.created_at.desc()).limit(5))).scalars().all()
        for j in jobs:
            print(f"JOB: {j.id} | source: {j.source} | status: {j.status} | end_reason: {j.end_reason} | query: {j.query} | stats: {j.statistics}")
            obs = (await session.execute(select(ProspectObservation).where(ProspectObservation.job_id == j.id))).scalars().all()
            print(f"  OBSERVATIONS COUNT: {len(obs)}")
            for o in obs[:3]:
                txt_len = len(o.visible_text or '')
                print(f"    URL: {o.url} | text len: {txt_len} | title: {o.page_title}")
                if o.metadata_json and 'content_units' in o.metadata_json:
                    units = o.metadata_json['content_units'] or []
                    print(f"    CONTENT UNITS: {len(units)}")
                    for u in units[:3]:
                        print(f"      UNIT: {u.get('author')} | text: {u.get('text', '')[:100]}")
            cands = (await session.execute(select(ProspectCandidate).where(ProspectCandidate.job_id == j.id))).scalars().all()
            print(f"  CANDIDATES COUNT: {len(cands)}")
            for c in cands:
                print(f"    CANDIDATE: {c.username_or_handle} | status: {c.status} | evidence: {c.discovery_evidence[:100] if c.discovery_evidence else ''}")

asyncio.run(main())
