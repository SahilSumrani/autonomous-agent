from typing import Any, Dict, Optional, Type, Union
from pydantic import BaseModel
from packages.config.settings import settings
from services.api.app.core.logging import get_logger
from services.api.app.providers.ai.base import (
    AIProvider,
    AIProviderConfigError,
    AIProviderError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
)
from services.api.app.providers.ai.groq_provider import GroqProvider
from services.api.app.providers.ai.ollama_provider import OllamaProvider
from services.api.app.providers.ai.openai_provider import OpenAIProvider
from services.api.app.providers.ai.gemini_provider import GeminiProvider
from services.api.app.providers.ai.anthropic_provider import AnthropicProvider

logger = get_logger("ai_provider_factory")


class FallbackAIProvider(AIProvider):
    """
    Transparent failover wrapper that executes primary provider and
    fails over to secondary provider upon transient failures or timeouts.
    """

    def __init__(self, primary: AIProvider, fallback: Optional[AIProvider] = None) -> None:
        self.primary = primary
        self.fallback = fallback

    @property
    def provider_name(self) -> str:
        fb_name = self.fallback.provider_name if self.fallback else "none"
        return f"{self.primary.provider_name}_fallback_{fb_name}"

    @property
    def model_name(self) -> str:
        return self.primary.model_name

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str:
        try:
            return await self.primary.generate_text(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )
        except Exception as exc:
            if self.fallback:
                logger.warning(
                    "Primary AI provider failed, falling back to secondary",
                    primary=self.primary.provider_name,
                    fallback=self.fallback.provider_name,
                    error=str(exc),
                )
                return await self.fallback.generate_text(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs,
                )
            raise

    async def generate_structured(
        self,
        prompt: str,
        schema: Union[Type[BaseModel], Dict[str, Any]],
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.2,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        try:
            return await self.primary.generate_structured(
                prompt=prompt,
                schema=schema,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )
        except Exception as exc:
            if self.fallback:
                logger.warning(
                    "Primary AI provider failed structured generation, falling back",
                    primary=self.primary.provider_name,
                    fallback=self.fallback.provider_name,
                    error=str(exc),
                )
                return await self.fallback.generate_structured(
                    prompt=prompt,
                    schema=schema,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs,
                )
            raise

    async def health_check(self) -> bool:
        if await self.primary.health_check():
            return True
        if self.fallback:
            return await self.fallback.health_check()
        return False


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


def get_ai_provider_with_fallback(
    primary_name: Optional[str] = None,
    fallback_name: Optional[str] = None,
) -> AIProvider:
    """Instantiate primary provider with optional fallback provider."""
    primary = get_ai_provider(primary_name)
    fb = None
    if fallback_name:
        try:
            fb = get_ai_provider(fallback_name)
        except Exception as e:
            logger.warning("Could not initialize fallback AI provider", fallback_name=fallback_name, error=str(e))
    return FallbackAIProvider(primary=primary, fallback=fb)
