# Groq AI Provider Integration

## Overview

The TechVerse AI Client Acquisition OS integrates **Groq** as an ultra-fast cloud inference provider alongside **Ollama** (offline/local-first fallback).

Groq provides low-latency execution (<550ms) for high-frequency sales intelligence tasks, context analysis, message personalization, and reply formulation.

---

## Architecture & Provider Abstraction

Groq conforms strictly to the unified `AIProvider` contract in `services/api/app/providers/ai/`:

```text
AIProvider (services/api/app/providers/ai/base.py)
├── GroqProvider (services/api/app/providers/ai/groq_provider.py)
├── OllamaProvider (services/api/app/providers/ai/ollama_provider.py)
├── OpenAIProvider (services/api/app/providers/ai/openai_provider.py)
├── GeminiProvider (services/api/app/providers/ai/gemini_provider.py)
└── AnthropicProvider (services/api/app/providers/ai/anthropic_provider.py)
```

Factory instantiation is managed via:
```python
from services.api.app.providers.ai import get_ai_provider

provider = get_ai_provider()  # Resolves from AI_PROVIDER setting
```

---

## Environment Variables

Configure Groq in your `.env` file:

| Variable | Description | Default | Example |
|---|---|---|---|
| `AI_PROVIDER` | Active AI provider identifier | `groq` | `groq` or `ollama` |
| `GROQ_API_KEY` | GroqCloud API Authentication Key | `None` | `gsk_...` |
| `GROQ_MODEL` | Active production Groq model | `openai/gpt-oss-120b` | `openai/gpt-oss-120b`, `qwen/qwen3.8-27b` |
| `GROQ_TIMEOUT_SECONDS` | Bounded request timeout | `30.0` | `30.0` |
| `AI_FALLBACK_PROVIDER` | Fallback provider when offline | `ollama` | `ollama` |

> [!WARNING]
> Never hardcode or commit `GROQ_API_KEY`. It is read strictly from the runtime environment and masked in structured logs.

---

## Model Selection

Groq production models supported in the OS:

- **`openai/gpt-oss-120b`** (Default): High-capability reasoning and structured generation.
- **`qwen/qwen3.8-27b`**: Ultra-low-latency text and JSON completions (~108ms).
- **`openai/gpt-oss-20b`**: Compact reasoning model.

Configure models via `GROQ_MODEL` without code changes.

---

## Fallback & Resilience Strategy

If Groq encounters rate limiting (`429`), temporary upstream outages (`5xx`), or network timeouts:
1. **Bounded Exponential Backoff**: Retries up to 2 times with jitter.
2. **Safe Error Escalation**: Raises typed errors (`AIProviderRateLimitError`, `AIProviderTimeoutError`, `AIProviderAuthError`).
3. **Deterministic Fallbacks**: Heuristic validators and offline rules prevent fabrication. Approval gates and human verification are never bypassed.

---

## Security & Isolation

- **Secret Redaction**: Structured logging filters `groq_api_key` and auth headers via `filter_sensitive_data`.
- **Extension Isolation**: No API keys or external Groq URLs are ever packaged into `apps/browser-extension/dist`.
- **Prompt Injection Defense**: Inbound prospect data is treated as untrusted text. Structured outputs are strictly validated via Pydantic models.
- **Zero Autonomous Dispatch**: AI generates drafts; human approval gates remain mandatory before any browser or messaging actions can execute.

---

## Verification & Testing

Run unit & mock test suites:
```powershell
.venv\Scripts\python.exe -m pytest tests/test_ai_providers.py -v
```

Run provider performance benchmark:
```powershell
.venv\Scripts\python.exe scripts/benchmark_providers.py
```
