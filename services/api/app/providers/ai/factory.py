from typing import Optional
from packages.config.settings import settings
from services.api.app.providers.ai.base import AIProvider, AIProviderConfigError
from services.api.app.providers.ai.groq_provider import GroqProvider
from services.api.app.providers.ai.ollama_provider import OllamaProvider
from services.api.app.providers.ai.openai_provider import OpenAIProvider
from services.api.app.providers.ai.gemini_provider import GeminiProvider
from services.api.app.providers.ai.anthropic_provider import AnthropicProvider


def get_ai_provider(provider_name: Optional[str] = None) -> AIProvider:
    """
    Factory function to instantiate the configured AI provider.
    Fails safely with AIProviderConfigError if the provider is unsupported or misconfigured.
    """
    selected = (provider_name or settings.AI_PROVIDER).strip().lower()

    if selected == "groq":
        return GroqProvider()
    elif selected == "ollama":
        return OllamaProvider()
    elif selected == "openai":
        return OpenAIProvider()
    elif selected == "gemini":
        return GeminiProvider()
    elif selected == "anthropic":
        return AnthropicProvider()
    else:
        raise AIProviderConfigError(f"Unsupported AI provider: '{selected}'. Supported: groq, ollama, openai, gemini, anthropic.")
