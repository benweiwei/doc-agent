"""Tool system for the doc-agent agent loop."""

from __future__ import annotations

from doc_agent.tools.base import Tool, ToolRegistry
from doc_agent.tools.document_tools import build_document_tools
from doc_agent.tools.web_search import WebSearchTool

__all__ = [
    "Tool",
    "ToolRegistry",
    "build_document_tools",
    "WebSearchTool",
]
