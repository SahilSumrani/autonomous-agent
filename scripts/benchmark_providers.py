import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from services.api.app.providers.ai import GroqProvider, OllamaProvider

async def benchmark():
    prompt = "Reply with one sentence summarizing why AI automation helps agencies."
    results = []

    # 1. Test Groq
    groq = GroqProvider()
    print("Testing Groq...")
    t0 = time.perf_counter()
    try:
        reply = await groq.generate_text(prompt, max_tokens=60)
        lat = (time.perf_counter() - t0) * 1000
        results.append({
            "provider": "Groq",
            "model": groq.model_name,
            "latency_ms": f"{lat:.1f}ms",
            "status": "SUCCESS",
            "sample": reply[:50] + "..."
        })
    except Exception as e:
        lat = (time.perf_counter() - t0) * 1000
        results.append({
            "provider": "Groq",
            "model": groq.model_name,
            "latency_ms": f"{lat:.1f}ms",
            "status": f"FAILED ({type(e).__name__})",
            "sample": str(e)
        })

    # 2. Test Ollama
    ollama = OllamaProvider(timeout_seconds=5.0)
    print("Testing Ollama...")
    t0 = time.perf_counter()
    try:
        reply = await ollama.generate_text(prompt, max_tokens=60)
        lat = (time.perf_counter() - t0) * 1000
        results.append({
            "provider": "Ollama",
            "model": ollama.model_name,
            "latency_ms": f"{lat:.1f}ms",
            "status": "SUCCESS",
            "sample": reply[:50] + "..."
        })
    except Exception as e:
        lat = (time.perf_counter() - t0) * 1000
        results.append({
            "provider": "Ollama",
            "model": ollama.model_name,
            "latency_ms": f"{lat:.1f}ms",
            "status": "OFFLINE / TIMEOUT",
            "sample": "Connection refused / local daemon not serving"
        })

    print("\n================== BENCHMARK RESULTS ==================")
    print(f"{'Provider':<10} | {'Model':<22} | {'Latency':<10} | {'Result':<18}")
    print("-" * 68)
    for r in results:
        print(f"{r['provider']:<10} | {r['model']:<22} | {r['latency_ms']:<10} | {r['status']:<18}")
    print("=======================================================\n")

if __name__ == "__main__":
    asyncio.run(benchmark())
