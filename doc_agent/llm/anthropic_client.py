"""Anthropic (Claude) LLM client."""

from __future__ import annotations

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


class AnthropicClient(LLMClient):
    """Client for Anthropic's Claude API."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key_env: str = "ANTHROPIC_API_KEY",
    ) -> None:
        self.model = model
        self.api_key_env = api_key_env
        self._api_key = os.environ.get(api_key_env, "")
        self._client: "AsyncAnthropic | None" = None  # type: ignore[name-defined]

    def _get_client(self):
        """Lazily initialize the Anthropic async client."""
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=self._api_key)
        return self._client

    def is_available(self) -> bool:
        """Check if the Anthropic API key is configured."""
        return bool(self._api_key)

    def supports_tools(self) -> bool:
        """Anthropic Messages API supports tool-calling."""
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
        """Tool-calling chat using the Anthropic Messages API."""
        import anthropic

        client = self._get_client()
        logger.debug(
            "anthropic.chat",
            model=self.model,
            n_messages=len(messages),
            n_tools=len(tools or []),
        )

        try:
            create_kwargs: dict = {
                "model": self.model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": self._to_anthropic_messages(messages),
            }
            if system:
                create_kwargs["system"] = system
            if tools:
                create_kwargs["tools"] = [
                    {
                        "name": t.name,
                        "description": t.description,
                        "input_schema": t.parameters or {"type": "object", "properties": {}},
                    }
                    for t in tools
                ]

            response = await client.messages.create(**create_kwargs)

            text_parts: list[str] = []
            tool_calls: list[ToolCall] = []
            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "tool_use":
                    tool_calls.append(
                        ToolCall(
                            id=block.id,
                            name=block.name,
                            arguments=dict(block.input or {}),
                        )
                    )

            usage = {}
            if getattr(response, "usage", None) is not None:
                usage = {
                    "input_tokens": getattr(response.usage, "input_tokens", 0),
                    "output_tokens": getattr(response.usage, "output_tokens", 0),
                }

            return ChatResult(
                text="".join(text_parts),
                tool_calls=tool_calls,
                stop_reason=getattr(response, "stop_reason", None),
                usage=usage,
            )

        except anthropic.APITimeoutError as e:
            logger.error("anthropic.chat.timeout", error=str(e))
            raise LLMTimeoutError(str(e), provider="anthropic") from e
        except anthropic.RateLimitError as e:
            logger.error("anthropic.chat.rate_limit", error=str(e))
            raise LLMRateLimitError(str(e), provider="anthropic") from e
        except anthropic.APIStatusError as e:
            if e.status_code >= 500:
                logger.error("anthropic.chat.server_error", status=e.status_code, error=str(e))
                raise LLMUnavailableError(str(e), provider="anthropic") from e
            logger.error("anthropic.chat.api_error", status=e.status_code, error=str(e))
            raise LLMError(str(e), provider="anthropic") from e
        except anthropic.APIConnectionError as e:
            logger.error("anthropic.chat.connection_error", error=str(e))
            raise LLMUnavailableError(str(e), provider="anthropic") from e

    @staticmethod
    def _to_anthropic_messages(messages: list[ChatMessage]) -> list[dict]:
        """Convert normalized ChatMessage list into Anthropic message dicts."""
        result: list[dict] = []
        for msg in messages:
            if msg.role == "tool":
                result.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.tool_call_id,
                                "content": msg.content,
                            }
                        ],
                    }
                )
            elif msg.role == "assistant" and msg.tool_calls:
                blocks: list[dict] = []
                if msg.content:
                    blocks.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments,
                        }
                    )
                result.append({"role": "assistant", "content": blocks})
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
        """Generate a completion using Claude."""
        import anthropic

        client = self._get_client()
        logger.debug(
            "anthropic.generate",
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        try:
            messages = [{"role": "user", "content": prompt}]
            create_kwargs: dict = {
                "model": self.model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages,
            }
            if system:
                create_kwargs["system"] = system

            response = await client.messages.create(**create_kwargs)

            # Extract text from content blocks
            text_parts = []
            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
            return "".join(text_parts)

        except anthropic.APITimeoutError as e:
            logger.error("anthropic.timeout", error=str(e))
            raise LLMTimeoutError(str(e), provider="anthropic") from e
        except anthropic.RateLimitError as e:
            logger.error("anthropic.rate_limit", error=str(e))
            raise LLMRateLimitError(str(e), provider="anthropic") from e
        except anthropic.APIStatusError as e:
            if e.status_code >= 500:
                logger.error("anthropic.server_error", status=e.status_code, error=str(e))
                raise LLMUnavailableError(str(e), provider="anthropic") from e
            logger.error("anthropic.api_error", status=e.status_code, error=str(e))
            raise LLMError(str(e), provider="anthropic") from e
        except anthropic.APIConnectionError as e:
            logger.error("anthropic.connection_error", error=str(e))
            raise LLMUnavailableError(str(e), provider="anthropic") from e

    async def generate_stream(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Stream a completion using Claude."""
        import anthropic

        client = self._get_client()
        logger.debug(
            "anthropic.generate_stream",
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        try:
            messages = [{"role": "user", "content": prompt}]
            create_kwargs: dict = {
                "model": self.model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages,
            }
            if system:
                create_kwargs["system"] = system

            async with client.messages.stream(**create_kwargs) as stream:
                async for text in stream.text_stream:
                    yield text

        except anthropic.APITimeoutError as e:
            logger.error("anthropic.stream.timeout", error=str(e))
            raise LLMTimeoutError(str(e), provider="anthropic") from e
        except anthropic.RateLimitError as e:
            logger.error("anthropic.stream.rate_limit", error=str(e))
            raise LLMRateLimitError(str(e), provider="anthropic") from e
        except anthropic.APIStatusError as e:
            if e.status_code >= 500:
                logger.error(
                    "anthropic.stream.server_error", status=e.status_code, error=str(e)
                )
                raise LLMUnavailableError(str(e), provider="anthropic") from e
            logger.error("anthropic.stream.api_error", status=e.status_code, error=str(e))
            raise LLMError(str(e), provider="anthropic") from e
        except anthropic.APIConnectionError as e:
            logger.error("anthropic.stream.connection_error", error=str(e))
            raise LLMUnavailableError(str(e), provider="anthropic") from e
