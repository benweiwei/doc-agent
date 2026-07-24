"""Base LLM client interface and error types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Optional


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


# ─── Tool-calling Data Structures ──────────────────────────────────────────────


@dataclass
class ToolSpec:
    """与 Provider 无关的工具声明。

    Attributes:
        name: 工具名称。
        description: 工具用途描述（供模型理解何时调用）。
        parameters: JSON Schema 描述的参数结构。
    """

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCall:
    """模型发起的一次工具调用。"""

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatMessage:
    """对话消息（与 Provider 无关的规范化表示）。

    role:
        - "user" / "assistant": 普通对话消息，内容在 content。
        - "tool": 工具执行结果，content 为结果文本，tool_call_id 关联对应调用。
    assistant 触发工具调用时，tool_calls 记录调用列表。
    """

    role: str
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: Optional[str] = None


@dataclass
class ChatResult:
    """一次 chat 调用的规范化返回。"""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: Optional[str] = None
    usage: dict[str, Any] = field(default_factory=dict)


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

    def supports_tools(self) -> bool:
        """是否支持工具调用（Agent Loop）。

        默认 False；支持 tool-calling 的实现需覆写为 True。
        """
        return False

    async def chat(
        self,
        messages: list[ChatMessage],
        system: str = "",
        tools: Optional[list[ToolSpec]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs,
    ) -> ChatResult:
        """带工具调用能力的多轮对话接口。

        Args:
            messages: 规范化的对话消息列表。
            system: 系统提示词。
            tools: 可供模型调用的工具声明列表。
            max_tokens: 最大生成 token 数。
            temperature: 生成温度。

        Returns:
            ChatResult，包含文本和/或工具调用请求。

        Raises:
            LLMError: 请求失败或该 Provider 不支持工具调用时抛出。
        """
        raise LLMError(
            "This provider does not support tool-calling chat",
            provider=getattr(self, "model", "unknown"),
        )


# Keep backward compat alias
BaseLLMClient = LLMClient
