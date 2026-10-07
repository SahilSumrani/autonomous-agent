from typing import Any, Dict, Optional, Type, Union
from pydantic import BaseModel
from packages.config.settings import settings
from services.api.app.providers.ai.base import (
    AIProvider,
    AIProviderConfigError,
)


class GeminiProvider(AIProvider):
    """Google Gemini AI provider."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-1.5-pro") -> None:
        self._api_key = api_key or settings.GEMINI_API_KEY
        if not self._api_key:
            raise AIProviderConfigError("GeminiProvider requires GEMINI_API_KEY.")
        self._model = model

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None, **kwargs: Any) -> str:
        raise NotImplementedError("GeminiProvider integration stub")

    async def generate_structured(self, prompt: str, schema: Union[Type[BaseModel], Dict[str, Any]], system_prompt: Optional[str] = None, **kwargs: Any) -> Dict[str, Any]:
        raise NotImplementedError("GeminiProvider integration stub")

    async def health_check(self) -> bool:
        return bool(self._api_key)
