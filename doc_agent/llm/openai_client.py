"""OpenAI LLM client."""

from __future__ import annotations

import os
from typing import AsyncGenerator

import structlog

from doc_agent.llm.base import (
    LLMClient,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMUnavailableError,
)

logger = structlog.get_logger(__name__)


class OpenAIClient(LLMClient):
    """Client for OpenAI's API."""

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key_env: str = "OPENAI_API_KEY",
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.model = model
        self.api_key_env = api_key_env
        self._api_key = api_key or os.environ.get(api_key_env, "")
        self._base_url = base_url
        self._client: "AsyncOpenAI | None" = None  # type: ignore[name-defined]

    def _get_client(self):
        """Lazily initialize the OpenAI async client."""
        if self._client is None:
            from openai import AsyncOpenAI

            kwargs: dict = {"api_key": self._api_key}
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = AsyncOpenAI(**kwargs)
        return self._client

    def is_available(self) -> bool:
        """Check if the OpenAI API key is configured."""
        return bool(self._api_key)

    async def generate(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs,
    ) -> str:
        """Generate a completion using OpenAI."""
        import openai

        client = self._get_client()
        logger.debug(
            "openai.generate",
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        try:
            messages: list[dict] = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            response = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            choice = response.choices[0]
            return choice.message.content or ""

        except openai.APITimeoutError as e:
            logger.error("openai.timeout", error=str(e))
            raise LLMTimeoutError(str(e), provider="openai") from e
        except openai.RateLimitError as e:
            logger.error("openai.rate_limit", error=str(e))
            raise LLMRateLimitError(str(e), provider="openai") from e
        except openai.APIStatusError as e:
            if e.status_code >= 500:
                logger.error("openai.server_error", status=e.status_code, error=str(e))
                raise LLMUnavailableError(str(e), provider="openai") from e
            logger.error("openai.api_error", status=e.status_code, error=str(e))
            raise LLMError(str(e), provider="openai") from e
        except openai.APIConnectionError as e:
            logger.error("openai.connection_error", error=str(e))
            raise LLMUnavailableError(str(e), provider="openai") from e

    async def generate_stream(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Stream a completion using OpenAI."""
        import openai

        client = self._get_client()
        logger.debug(
            "openai.generate_stream",
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        try:
            messages: list[dict] = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            stream = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except openai.APITimeoutError as e:
            logger.error("openai.stream.timeout", error=str(e))
            raise LLMTimeoutError(str(e), provider="openai") from e
        except openai.RateLimitError as e:
            logger.error("openai.stream.rate_limit", error=str(e))
            raise LLMRateLimitError(str(e), provider="openai") from e
        except openai.APIStatusError as e:
            if e.status_code >= 500:
                logger.error(
                    "openai.stream.server_error", status=e.status_code, error=str(e)
                )
                raise LLMUnavailableError(str(e), provider="openai") from e
            logger.error("openai.stream.api_error", status=e.status_code, error=str(e))
            raise LLMError(str(e), provider="openai") from e
        except openai.APIConnectionError as e:
            logger.error("openai.stream.connection_error", error=str(e))
            raise LLMUnavailableError(str(e), provider="openai") from e
