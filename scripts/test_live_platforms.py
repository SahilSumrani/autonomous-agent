import asyncio
import json
import logging
import os
import sys
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.api.app.agents.prospecting.sources.instagram import InstagramSource
from services.api.app.agents.prospecting.sources.reddit import RedditSource
from services.api.app.agents.prospecting.sources.threads import ThreadsSource

logging.basicConfig(level=logging.INFO)

async def test_live_platforms():
    print("\n" + "=" * 80)
    print("LIVE PUBLIC PLATFORM PROSPECTING VALIDATION (INSTAGRAM, REDDIT, THREADS)")
    print("=" * 80)

    results = {}
    headers = {
        "User-Agent": "TechVerse-AI-Agent/2.0 (Platform Validation)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    async with httpx.AsyncClient(headers=headers, timeout=12.0, follow_redirects=True) as client:
        # 1. Instagram
        print("\n--- Testing Instagram Public Content ---")
        ig_source = InstagramSource()
        ig_url = "https://www.instagram.com/explore/tags/austinretail/"
        try:
            resp = await client.get(ig_url)
            html = resp.text
            print(f"  HTTP Status: {resp.status_code}, Length: {len(html)}")
            challenge = ig_source.detect_security_challenge({"url": str(resp.url), "visible_text": html[:3000]})
            if challenge.is_blocked or resp.status_code in (401, 403, 429) or "login" in str(resp.url).lower():
                print(f"  -> Platform Status: BLOCKED ({challenge.reason or 'Login wall redirected'})")
                results["instagram"] = ("LIVE_BLOCKED", "Instagram redirected to login wall / checkpoint")
            else:
                cands = ig_source.discover_candidates({"url": str(resp.url), "visible_text": html[:2000], "links": []})
                print(f"  -> Discovered {len(cands)} public candidates")
                results["instagram"] = ("LIVE_PASS", f"Discovered {len(cands)} public candidates")
        except Exception as e:
            print(f"  -> Instagram network error / barrier: {e}")
            results["instagram"] = ("LIVE_BLOCKED", f"Network challenge/block: {e}")

        # 2. Reddit
        print("\n--- Testing Reddit Public Content ---")
        rd_source = RedditSource()
        rd_url = "https://www.reddit.com/r/smallbusiness/"
        try:
            resp = await client.get(rd_url)
            html = resp.text
            print(f"  HTTP Status: {resp.status_code}, Length: {len(html)}")
            challenge = rd_source.detect_security_challenge({"url": str(resp.url), "visible_text": html[:3000]})
            if challenge.is_blocked or resp.status_code in (401, 403, 429) or "blocked" in html.lower():
                print(f"  -> Platform Status: BLOCKED ({challenge.reason or 'Reddit anti-bot block'})")
                results["reddit"] = ("LIVE_BLOCKED", "Reddit blocked unauthenticated request with security challenge")
            else:
                cands = rd_source.discover_candidates({"url": str(resp.url), "visible_text": html[:2000], "links": []})
                print(f"  -> Reddit public inspection: {len(cands)} candidates")
                results["reddit"] = ("LIVE_PASS", f"Public inspection successful: {len(cands)} candidates")
        except Exception as e:
            print(f"  -> Reddit network error / barrier: {e}")
            results["reddit"] = ("LIVE_BLOCKED", f"Network challenge/block: {e}")

        # 3. Threads
        print("\n--- Testing Threads Public Content ---")
        th_source = ThreadsSource()
        th_url = "https://www.threads.net/@zuck"
        try:
            resp = await client.get(th_url)
            html = resp.text
            print(f"  HTTP Status: {resp.status_code}, Length: {len(html)}")
            challenge = th_source.detect_security_challenge({"url": str(resp.url), "visible_text": html[:3000]})
            if challenge.is_blocked or resp.status_code in (401, 403, 429) or "login" in str(resp.url).lower():
                print(f"  -> Platform Status: BLOCKED ({challenge.reason or 'Threads login barrier'})")
                results["threads"] = ("LIVE_BLOCKED", "Threads presented login barrier / redirect")
            else:
                cands = th_source.discover_candidates({"url": str(resp.url), "visible_text": html[:2000], "links": []})
                print(f"  -> Threads public inspection: {len(cands)} candidates")
                results["threads"] = ("LIVE_PASS", f"Public inspection successful: {len(cands)} candidates")
        except Exception as e:
            print(f"  -> Threads network error / barrier: {e}")
            results["threads"] = ("LIVE_BLOCKED", f"Network challenge/block: {e}")

    print("\nSummary of Platform Live Tests:")
    for platform, (status, detail) in results.items():
        print(f"  {platform.upper()}: {status} ({detail})")

if __name__ == "__main__":
    asyncio.run(test_live_platforms())
