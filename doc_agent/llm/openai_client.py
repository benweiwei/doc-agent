"""OpenAI LLM client."""

from __future__ import annotations

import json
import os
from typing import AsyncGenerator, Optional

import structlog

from doc_agent.llm.base import (
    ChatMessage,
    ChatResult,
    LLMClient,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMUnavailableError,
    ToolCall,
    ToolSpec,
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

    def supports_tools(self) -> bool:
        """OpenAI Chat Completions API supports function calling."""
        return True

    async def chat(
        self,
        messages: list[ChatMessage],
        system: str = "",
        tools: Optional[list[ToolSpec]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs,
    ) -> ChatResult:
        """Tool-calling chat using the OpenAI Chat Completions API."""
        import openai

        client = self._get_client()
        logger.debug(
            "openai.chat",
            model=self.model,
            n_messages=len(messages),
            n_tools=len(tools or []),
        )

        try:
            oai_messages: list[dict] = []
            if system:
                oai_messages.append({"role": "system", "content": system})
            oai_messages.extend(self._to_openai_messages(messages))

            create_kwargs: dict = {
                "model": self.model,
                "messages": oai_messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if tools:
                create_kwargs["tools"] = [
                    {
                        "type": "function",
                        "function": {
                            "name": t.name,
                            "description": t.description,
                            "parameters": t.parameters or {"type": "object", "properties": {}},
                        },
                    }
                    for t in tools
                ]

            response = await client.chat.completions.create(**create_kwargs)
            choice = response.choices[0]
            message = choice.message

            tool_calls: list[ToolCall] = []
            for tc in message.tool_calls or []:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(
                    ToolCall(id=tc.id, name=tc.function.name, arguments=args)
                )

            usage = {}
            if getattr(response, "usage", None) is not None:
                usage = {
                    "input_tokens": getattr(response.usage, "prompt_tokens", 0),
                    "output_tokens": getattr(response.usage, "completion_tokens", 0),
                }

            return ChatResult(
                text=message.content or "",
                tool_calls=tool_calls,
                stop_reason=choice.finish_reason,
                usage=usage,
            )

        except openai.APITimeoutError as e:
            logger.error("openai.chat.timeout", error=str(e))
            raise LLMTimeoutError(str(e), provider="openai") from e
        except openai.RateLimitError as e:
            logger.error("openai.chat.rate_limit", error=str(e))
            raise LLMRateLimitError(str(e), provider="openai") from e
        except openai.APIStatusError as e:
            if e.status_code >= 500:
                logger.error("openai.chat.server_error", status=e.status_code, error=str(e))
                raise LLMUnavailableError(str(e), provider="openai") from e
            logger.error("openai.chat.api_error", status=e.status_code, error=str(e))
            raise LLMError(str(e), provider="openai") from e
        except openai.APIConnectionError as e:
            logger.error("openai.chat.connection_error", error=str(e))
            raise LLMUnavailableError(str(e), provider="openai") from e

    @staticmethod
    def _to_openai_messages(messages: list[ChatMessage]) -> list[dict]:
        """Convert normalized ChatMessage list into OpenAI message dicts."""
        result: list[dict] = []
        for msg in messages:
            if msg.role == "tool":
                result.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.tool_call_id,
                        "content": msg.content,
                    }
                )
            elif msg.role == "assistant" and msg.tool_calls:
                result.append(
                    {
                        "role": "assistant",
                        "content": msg.content or None,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.name,
                                    "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                                },
                            }
                            for tc in msg.tool_calls
                        ],
                    }
                )
            else:
                result.append({"role": msg.role, "content": msg.content})
        return result

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
