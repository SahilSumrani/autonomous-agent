import asyncio
import json
from typing import Any, Dict, List, Optional, Type, Union
import httpx
from pydantic import BaseModel, ValidationError

from packages.config.settings import settings
from services.api.app.core.logging import get_logger
from services.api.app.providers.ai.base import (
    AIProvider,
    AIProviderAuthError,
    AIProviderConfigError,
    AIProviderError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
)

logger = get_logger("groq_provider")

GROQ_API_BASE_URL = "https://api.groq.com/openai/v1"


class GroqProvider(AIProvider):
    """
    High-performance cloud AI provider using Groq's low-latency inference engine
    via official OpenAI-compatible chat completions API.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        base_url: str = GROQ_API_BASE_URL,
    ) -> None:
        self._api_key = api_key if api_key is not None else settings.GROQ_API_KEY
        if not self._api_key or not self._api_key.strip():
            raise AIProviderConfigError(
                "GroqProvider requires a valid GROQ_API_KEY. None configured in environment."
            )

        self._model = (model or settings.GROQ_MODEL or "openai/gpt-oss-120b").strip()
        if not self._model:
            raise AIProviderConfigError("GroqProvider requires a non-empty model identifier.")

        self._timeout = float(timeout_seconds if timeout_seconds is not None else settings.GROQ_TIMEOUT_SECONDS)
        self._base_url = base_url.rstrip("/")

    @property
    def provider_name(self) -> str:
        return "groq"

    @property
    def model_name(self) -> str:
        return self._model

    def __repr__(self) -> str:
        # Prevent secret exposure in repr
        return f"<GroqProvider(model='{self._model}', timeout={self._timeout}s)>"

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "User-Agent": "TechVerse-AI/2.0",
        }

    async def _post_chat_completion(
        self,
        payload: Dict[str, Any],
        max_retries: int = 2,
    ) -> Dict[str, Any]:
        """Execute chat completion request with bounded retry on transient errors."""
        url = f"{self._base_url}/chat/completions"
        headers = self._get_headers()
        attempt = 0

        while attempt <= max_retries:
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(url, json=payload, headers=headers)

                if response.status_code == 200:
                    return response.json()

                if response.status_code == 401 or response.status_code == 403:
                    logger.error("Groq authentication failed", status_code=response.status_code)
                    raise AIProviderAuthError(
                        f"Groq API authentication rejected (HTTP {response.status_code}). Verify GROQ_API_KEY."
                    )

                if response.status_code == 429:
                    attempt += 1
                    if attempt <= max_retries:
                        backoff = 0.5 * (2 ** (attempt - 1))
                        logger.warning("Groq rate limit encountered. Retrying with backoff", attempt=attempt, backoff=backoff)
                        await asyncio.sleep(backoff)
                        continue
                    raise AIProviderRateLimitError("Groq API rate limit exceeded (HTTP 429). Retries exhausted.")

                if response.status_code >= 500:
                    attempt += 1
                    if attempt <= max_retries:
                        backoff = 0.5 * (2 ** (attempt - 1))
                        logger.warning("Groq server error. Retrying with backoff", status_code=response.status_code, attempt=attempt)
                        await asyncio.sleep(backoff)
                        continue
                    raise AIProviderError(f"Groq server error (HTTP {response.status_code}): {response.text}")

                raise AIProviderError(f"Groq API returned HTTP {response.status_code}: {response.text}")

            except httpx.TimeoutException as exc:
                attempt += 1
                if attempt <= max_retries:
                    await asyncio.sleep(0.5)
                    continue
                raise AIProviderTimeoutError(f"Groq request timed out after {self._timeout}s.") from exc
            except (AIProviderError, AIProviderAuthError, AIProviderRateLimitError, AIProviderTimeoutError):
                raise
            except Exception as exc:
                attempt += 1
                if attempt <= max_retries:
                    await asyncio.sleep(0.5)
                    continue
                raise AIProviderError(f"Network error communicating with Groq: {type(exc).__name__}") from exc

        raise AIProviderError("Groq request failed: max retries exceeded.")

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str:
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            **kwargs,
        }

        data = await self._post_chat_completion(payload)
        choices = data.get("choices", [])
        if not choices:
            raise AIProviderError("Groq response did not contain any completion choices.")

        content = choices[0].get("message", {}).get("content", "")
        return content.strip()

    async def generate_structured(
        self,
        prompt: str,
        schema: Union[Type[BaseModel], Dict[str, Any]],
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.2,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        sys_msg = system_prompt or "You are a precise data extraction assistant."
        schema_desc = ""
        if isinstance(schema, type) and issubclass(schema, BaseModel):
            schema_desc = json.dumps(schema.model_json_schema(), indent=2)
        elif isinstance(schema, dict):
            schema_desc = json.dumps(schema, indent=2)

        augmented_system = (
            f"{sys_msg}\n\n"
            f"You MUST respond ONLY with a single valid JSON object strictly complying with this schema:\n"
            f"{schema_desc}\n"
            f"Do not include any text, reasoning, or markdown ticks outside the JSON object."
        )

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": augmented_system},
            {"role": "user", "content": prompt},
        ]

        payload = {
            "model": self._model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "max_tokens": max_tokens,
            "temperature": temperature,
            **kwargs,
        }

        data = await self._post_chat_completion(payload)
        choices = data.get("choices", [])
        if not choices:
            raise AIProviderError("Groq response did not contain any completion choices.")

        raw_content = choices[0].get("message", {}).get("content", "").strip()
        if not raw_content:
            raise AIProviderError("Groq returned empty response for structured generation.")

        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            raise AIProviderError(f"Groq returned malformed JSON: {raw_content[:100]}...") from exc

        if isinstance(schema, type) and issubclass(schema, BaseModel):
            try:
                validated = schema.model_validate(parsed)
                return validated.model_dump()
            except ValidationError as exc:
                raise AIProviderError(f"Structured output failed schema validation: {exc}") from exc

        return parsed

    async def health_check(self) -> bool:
        """Perform a lightweight ping to verify API key validity and endpoint availability."""
        url = f"{self._base_url}/models"
        headers = self._get_headers()
        try:
            async with httpx.AsyncClient(timeout=min(self._timeout, 5.0)) as client:
                res = await client.get(url, headers=headers)
                return res.status_code == 200
        except Exception as exc:
            logger.warning("Groq health check failed", error=str(exc))
            return False
