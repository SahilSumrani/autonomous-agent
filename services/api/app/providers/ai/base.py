import abc
from typing import Any, Dict, Optional, Type, Union
from pydantic import BaseModel


class AIProviderError(Exception):
    """Base exception for all AI provider errors."""
    pass


class AIProviderConfigError(AIProviderError):
    """Raised when an AI provider is misconfigured or lacks credentials."""
    pass


class AIProviderTimeoutError(AIProviderError):
    """Raised when an AI provider request times out."""
    pass


class AIProviderRateLimitError(AIProviderError):
    """Raised when an AI provider responds with a rate limit (429)."""
    pass


class AIProviderAuthError(AIProviderError):
    """Raised when AI provider authentication fails (401/403)."""
    pass


class AIProvider(abc.ABC):
    """
    Abstract base interface for all AI text & structured generation providers.
    All implementations (Groq, Ollama, OpenAI, Gemini, Anthropic) must conform to this contract.
    """

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Unique provider identifier (e.g. 'groq', 'ollama')."""
        pass

    @property
    @abc.abstractmethod
    def model_name(self) -> str:
        """Name of the currently configured model for this provider."""
        pass

    @abc.abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str:
        """Generate unstructured text completion."""
        pass

    @abc.abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        schema: Union[Type[BaseModel], Dict[str, Any]],
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.2,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Generate structured JSON output validated against schema."""
        pass

    @abc.abstractmethod
    async def health_check(self) -> bool:
        """Check availability and connectivity of the provider."""
        pass
