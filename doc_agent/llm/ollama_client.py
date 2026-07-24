"""Ollama (local) LLM client."""

from __future__ import annotations

from typing import AsyncGenerator

import httpx
import structlog

from doc_agent.llm.base import (
    LLMClient,
    LLMError,
    LLMTimeoutError,
    LLMUnavailableError,
)

logger = structlog.get_logger(__name__)


class OllamaClient(LLMClient):
    """Client for local Ollama API."""

    def __init__(
        self,
        model: str = "llama3",
        endpoint: str = "http://localhost:11434",
    ) -> None:
        self.model = model
        self.endpoint = endpoint.rstrip("/")

    def is_available(self) -> bool:
        """Check if the Ollama service is running (synchronous check)."""
        try:
            with httpx.Client(timeout=2.0) as client:
                resp = client.get(f"{self.endpoint}/api/tags")
                return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    def supports_tools(self) -> bool:
        """Ollama tool-calling is not supported yet."""
        return False

    async def chat(self, *args, **kwargs):
        """Tool-calling chat is not supported for the local Ollama backend yet."""
        raise LLMError(
            "Ollama backend does not support tool-calling (Agent Loop) yet; "
            "use a cloud provider (anthropic/openai) for agent mode.",
            provider="ollama",
        )

    async def generate(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs,
    ) -> str:
        """Generate a completion using Ollama."""
        logger.debug(
            "ollama.generate",
            model=self.model,
            endpoint=self.endpoint,
            temperature=temperature,
        )

        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system:
            payload["system"] = system

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self.endpoint}/api/generate",
                    json=payload,
                )
                if resp.status_code >= 500:
                    raise LLMUnavailableError(
                        f"Ollama returned {resp.status_code}: {resp.text}",
                        provider="ollama",
                    )
                if resp.status_code != 200:
                    raise LLMError(
                        f"Ollama returned {resp.status_code}: {resp.text}",
                        provider="ollama",
                    )
                data = resp.json()
                return data.get("response", "")

        except httpx.TimeoutException as e:
            logger.error("ollama.timeout", error=str(e))
            raise LLMTimeoutError(str(e), provider="ollama") from e
        except httpx.ConnectError as e:
            logger.error("ollama.connection_error", error=str(e))
            raise LLMUnavailableError(
                f"Cannot connect to Ollama at {self.endpoint}: {e}",
                provider="ollama",
            ) from e

    async def generate_stream(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Stream a completion using Ollama."""
        logger.debug(
            "ollama.generate_stream",
            model=self.model,
            endpoint=self.endpoint,
            temperature=temperature,
        )

        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system:
            payload["system"] = system

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.endpoint}/api/generate",
                    json=payload,
                ) as resp:
                    if resp.status_code >= 500:
                        await resp.aread()
                        raise LLMUnavailableError(
                            f"Ollama returned {resp.status_code}",
                            provider="ollama",
                        )
                    if resp.status_code != 200:
                        await resp.aread()
                        raise LLMError(
                            f"Ollama returned {resp.status_code}: {resp.text}",
                            provider="ollama",
                        )

                    import json

                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        token = data.get("response", "")
                        if token:
                            yield token
                        # Stop if done
                        if data.get("done", False):
                            break

        except httpx.TimeoutException as e:
            logger.error("ollama.stream.timeout", error=str(e))
            raise LLMTimeoutError(str(e), provider="ollama") from e
        except httpx.ConnectError as e:
            logger.error("ollama.stream.connection_error", error=str(e))
            raise LLMUnavailableError(
                f"Cannot connect to Ollama at {self.endpoint}: {e}",
                provider="ollama",
            ) from e
