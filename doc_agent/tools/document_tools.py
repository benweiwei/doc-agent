"""Document-domain tools: read / list / search / apply_edit.

These tools wrap the VersionControl layer. Write operations (`apply_edit`) only
mutate an in-memory working copy shared with the AgentSession — nothing is
committed here. The user confirms and commits later via /api/edit/commit.
"""

from __future__ import annotations

import re
from typing import Optional

from doc_agent.tools.base import Tool
from doc_agent.vcs import DocumentNotFoundError, VersionControl


class _DocTool(Tool):
    """Base for document tools sharing vcs/branch/working_copy state."""

    def __init__(
        self,
        vcs: VersionControl,
        branch: Optional[str],
        working_copy: dict[str, str],
    ) -> None:
        self.vcs = vcs
        self.branch = branch
        #: 与 AgentSession 共享的工作副本 {doc_id: content}（未提交的编辑）。
        self.working_copy = working_copy

    def _current_content(self, doc_id: str) -> str:
        """Prefer the (uncommitted) working copy, else load from VCS."""
        if doc_id in self.working_copy:
            return self.working_copy[doc_id]
        content, _ = self.vcs.load_document(doc_id, self.branch)
        return content


class ReadDocumentTool(_DocTool):
    name = "read_document"
    description = "读取指定文档的完整内容。返回当前（含未提交编辑）的文本。"
    parameters = {
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string",
                "description": "文档 ID（文件路径，如 guide.md）",
            }
        },
        "required": ["document_id"],
    }

    async def run(self, document_id: str = "", **kwargs) -> str:
        if not document_id:
            return "Error: document_id is required"
        try:
            return self._current_content(document_id)
        except DocumentNotFoundError:
            return f"Error: document '{document_id}' not found on branch '{self.branch or 'current'}'"


class ListDocumentsTool(_DocTool):
    name = "list_documents"
    description = "列出当前分支下的所有文档 ID。"
    parameters = {"type": "object", "properties": {}}

    async def run(self, **kwargs) -> str:
        docs = self.vcs.list_documents(self.branch)
        if not docs:
            return "（无文档）"
        return "\n".join(docs)


class SearchDocumentsTool(_DocTool):
    name = "search_documents"
    description = (
        "在当前分支所有文档中搜索关键词，返回命中文档及匹配片段。"
        "默认大小写不敏感子串匹配，可设 regex=true 使用正则。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词或正则表达式"},
            "regex": {
                "type": "boolean",
                "description": "是否按正则匹配（默认 false）",
            },
        },
        "required": ["query"],
    }

    async def run(self, query: str = "", regex: bool = False, **kwargs) -> str:
        if not query:
            return "Error: query is required"

        try:
            pattern = re.compile(query if regex else re.escape(query), re.IGNORECASE)
        except re.error as e:
            return f"Error: invalid regex '{query}': {e}"

        docs = self.vcs.list_documents(self.branch)
        results: list[str] = []
        for doc_id in docs:
            try:
                content = self._current_content(doc_id)
            except DocumentNotFoundError:
                continue
            hits = []
            for i, line in enumerate(content.splitlines(), start=1):
                if pattern.search(line):
                    hits.append(f"  L{i}: {line.strip()}")
                    if len(hits) >= 5:
                        break
            if hits:
                results.append(f"## {doc_id}\n" + "\n".join(hits))

        if not results:
            return f"未找到匹配 '{query}' 的内容。"
        return "\n\n".join(results)


class ApplyEditTool(_DocTool):
    name = "apply_edit"
    description = (
        "用新内容替换指定文档的完整内容。改动仅写入内存工作副本，不会提交；"
        "用户会在界面确认后再提交。完成编辑任务后应调用本工具写入结果。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string",
                "description": "要编辑的文档 ID（文件路径）",
            },
            "new_content": {
                "type": "string",
                "description": "文档的完整新内容",
            },
        },
        "required": ["document_id", "new_content"],
    }

    async def run(self, document_id: str = "", new_content: str = "", **kwargs) -> str:
        if not document_id:
            return "Error: document_id is required"
        self.working_copy[document_id] = new_content
        n_lines = len(new_content.splitlines())
        return f"已将 '{document_id}' 的工作副本更新为 {n_lines} 行（待用户确认提交）。"


def build_document_tools(
    vcs: VersionControl,
    branch: Optional[str],
    working_copy: dict[str, str],
) -> list[Tool]:
    """Construct the document toolset bound to a session's shared state."""
    return [
        ReadDocumentTool(vcs, branch, working_copy),
        ListDocumentsTool(vcs, branch, working_copy),
        SearchDocumentsTool(vcs, branch, working_copy),
        ApplyEditTool(vcs, branch, working_copy),
    ]
