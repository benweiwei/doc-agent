"""Tool system: abstract Tool and ToolRegistry for the agent loop."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from doc_agent.llm.base import ToolSpec

logger = logging.getLogger(__name__)


class Tool(ABC):
    """Agent 可调用的工具抽象基类。

    子类需声明 name / description / parameters(JSON Schema) 并实现 run。
    """

    #: 工具名称（模型据此调用）。
    name: str = ""
    #: 工具用途描述。
    description: str = ""
    #: JSON Schema 描述的参数结构。
    parameters: dict[str, Any] = {"type": "object", "properties": {}}

    def spec(self) -> ToolSpec:
        """导出与 Provider 无关的工具声明。"""
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )

    @abstractmethod
    async def run(self, **kwargs) -> str:
        """执行工具并返回文本结果（供模型继续推理）。

        实现应避免抛出异常给调用方——由 ToolRegistry 统一兜底；
        但为清晰起见，实现内部可抛出，注册表会转成错误字符串。
        """
        ...


class ToolRegistry:
    """工具注册表：注册、分发调用、导出声明列表。"""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """注册一个工具（同名覆盖并告警）。"""
        if not tool.name:
            raise ValueError("Tool must have a non-empty name")
        if tool.name in self._tools:
            logger.warning("Tool '%s' already registered, overwriting", tool.name)
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """按名获取工具。"""
        return self._tools.get(name)

    def specs(self) -> list[ToolSpec]:
        """导出所有工具的 ToolSpec 列表（供 llm.chat 使用）。"""
        return [t.spec() for t in self._tools.values()]

    def __len__(self) -> int:
        return len(self._tools)

    async def execute(self, name: str, arguments: dict[str, Any]) -> str:
        """执行指定工具，异常统一转为给模型的错误字符串。

        Args:
            name: 工具名称。
            arguments: 参数字典。

        Returns:
            工具结果文本；工具不存在或执行出错时返回以 "Error:" 开头的文本。
        """
        tool = self._tools.get(name)
        if tool is None:
            return f"Error: unknown tool '{name}'"
        try:
            result = await tool.run(**(arguments or {}))
            return result if isinstance(result, str) else str(result)
        except TypeError as e:
            logger.warning("Tool '%s' invalid arguments: %s", name, e)
            return f"Error: invalid arguments for tool '{name}': {e}"
        except Exception as e:  # noqa: BLE001 - surface to model, never crash the loop
            logger.warning("Tool '%s' execution failed: %s", name, e)
            return f"Error: tool '{name}' failed: {e}"
