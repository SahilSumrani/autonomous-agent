import json
from typing import Any, Dict, List, Optional, Type, Union
import httpx
from pydantic import BaseModel, ValidationError

from packages.config.settings import settings
from services.api.app.core.logging import get_logger
from services.api.app.providers.ai.base import (
    AIProvider,
    AIProviderConfigError,
    AIProviderError,
    AIProviderTimeoutError,
)

logger = get_logger("ollama_provider")


class OllamaProvider(AIProvider):
    """
    Local-first offline AI provider using Ollama's HTTP API.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self._base_url = (base_url or settings.OLLAMA_BASE_URL or "http://localhost:11434").rstrip("/")
        self._model = (model or settings.OLLAMA_MODEL or "mistral").strip()
        if not self._model:
            raise AIProviderConfigError("OllamaProvider requires a non-empty model identifier.")
        self._timeout = timeout_seconds

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self._model

    def __repr__(self) -> str:
        return f"<OllamaProvider(model='{self._model}', base_url='{self._base_url}')>"

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str:
        url = f"{self._base_url}/api/generate"
        payload = {
            "model": self._model,
            "prompt": prompt,
            "system": system_prompt or "",
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            **kwargs,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                res = await client.post(url, json=payload)
            if res.status_code != 200:
                raise AIProviderError(f"Ollama returned HTTP {res.status_code}: {res.text}")
            data = res.json()
            return data.get("response", "").strip()
        except httpx.TimeoutException as exc:
            raise AIProviderTimeoutError(f"Ollama request timed out after {self._timeout}s.") from exc
        except Exception as exc:
            raise AIProviderError(f"Ollama connection error: {exc}") from exc

    async def generate_structured(
        self,
        prompt: str,
        schema: Union[Type[BaseModel], Dict[str, Any]],
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.2,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        url = f"{self._base_url}/api/generate"
        sys_msg = system_prompt or "Output valid JSON only."
        payload = {
            "model": self._model,
            "prompt": prompt,
            "system": sys_msg,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            **kwargs,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                res = await client.post(url, json=payload)
            if res.status_code != 200:
                raise AIProviderError(f"Ollama returned HTTP {res.status_code}: {res.text}")
            raw = res.json().get("response", "{}")
            parsed = json.loads(raw)
            if isinstance(schema, type) and issubclass(schema, BaseModel):
                validated = schema.model_validate(parsed)
                return validated.model_dump()
            return parsed
        except httpx.TimeoutException as exc:
            raise AIProviderTimeoutError(f"Ollama request timed out after {self._timeout}s.") from exc
        except (json.JSONDecodeError, ValidationError) as exc:
            raise AIProviderError(f"Ollama structured validation error: {exc}") from exc
        except Exception as exc:
            raise AIProviderError(f"Ollama connection error: {exc}") from exc

    async def health_check(self) -> bool:
        url = f"{self._base_url}/api/tags"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(url)
                return res.status_code == 200
        except Exception:
            return False
