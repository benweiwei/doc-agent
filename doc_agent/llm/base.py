"""Base LLM client interface and error types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncGenerator


# ─── Error Types ───────────────────────────────────────────────────────────────


class LLMError(Exception):
    """Base exception for LLM client errors."""

    def __init__(self, message: str, provider: str = "unknown") -> None:
        self.provider = provider
        super().__init__(f"[{provider}] {message}")


class LLMTimeoutError(LLMError):
    """Raised when an LLM request times out."""

    pass


class LLMRateLimitError(LLMError):
    """Raised when an LLM provider rate-limits the request."""

    def __init__(
        self, message: str, provider: str = "unknown", retry_after: float | None = None
    ) -> None:
        self.retry_after = retry_after
        super().__init__(message, provider)


class LLMUnavailableError(LLMError):
    """Raised when the LLM service is unavailable (5xx, connection refused, etc.)."""

    pass


# ─── Abstract Base Class ───────────────────────────────────────────────────────


class LLMClient(ABC):
    """LLM 客户端抽象基类。

    所有具体实现（Anthropic / OpenAI / Ollama）必须继承此类。
    """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs,
    ) -> str:
        """同步生成完整响应。

        Args:
            prompt: 用户输入的 prompt。
            system: 系统提示词。
            max_tokens: 最大生成 token 数。
            temperature: 生成温度。

        Returns:
            完整的模型响应文本。

        Raises:
            LLMError: 请求失败时抛出对应子类。
        """
        ...

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """流式生成响应，逐 token yield。

        Args:
            prompt: 用户输入的 prompt。
            system: 系统提示词。
            max_tokens: 最大生成 token 数。
            temperature: 生成温度。

        Yields:
            逐步生成的文本片段。

        Raises:
            LLMError: 请求失败时抛出对应子类。
        """
        ...
        # Make this a valid AsyncGenerator type
        yield  # type: ignore  # pragma: no cover

    @abstractmethod
    def is_available(self) -> bool:
        """检查服务是否可用。

        Returns:
            True 表示服务可用。
        """
        ...


# Keep backward compat alias
BaseLLMClient = LLMClient
