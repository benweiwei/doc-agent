"""Agent loop: multi-step tool-use editing session.

Drives an LLM through iterative tool calls (read/search/edit documents,
web search) until it produces a final edit. Nothing is committed here — the
loop only mutates an in-memory working copy and emits a final diff, which the
user confirms and commits via the existing /api/edit/commit flow.
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator, Optional

from doc_agent.agent import DocumentEditor
from doc_agent.config import AppConfig
from doc_agent.llm.base import ChatMessage
from doc_agent.models import EditRequest
from doc_agent.tools import ToolRegistry, WebSearchTool, build_document_tools
from doc_agent.vcs import DocumentNotFoundError

logger = logging.getLogger(__name__)


_AGENT_INSTRUCTIONS = (
    "\n\n## Agent 工作方式\n"
    "- 你可以调用工具来完成编辑任务：读取/列出/搜索文档、联网搜索资料。\n"
    "- 需要修改文档时，必须调用 `apply_edit` 写入完整的新内容（改动不会立即提交，用户会确认）。\n"
    "- 如果目标文档尚不存在或内容为空，说明用户想新建文档：直接根据指令撰写完整内容，"
    "然后调用 `apply_edit` 写入（首行用 `# 标题` 作为文档标题）。\n"
    "- 编辑完成后，用一句话简要说明你做了什么，然后结束（不再调用工具）。\n"
    "- 保持文档原有格式；只改与指令相关的部分。"
)


class AgentSession:
    """A single multi-step agent editing session.

    Composes a DocumentEditor to reuse prompt/diff/style helpers, and holds a
    shared working copy passed into the document tools.
    """

    def __init__(self, config: AppConfig, editor: Optional[DocumentEditor] = None) -> None:
        self.config = config
        self.editor = editor or DocumentEditor(config)
        self.llm = self.editor.llm
        self.vcs = self.editor.vcs
        self.working_copy: dict[str, str] = {}

    def _build_registry(self, branch: Optional[str]) -> ToolRegistry:
        registry = ToolRegistry()
        for tool in build_document_tools(self.vcs, branch, self.working_copy):
            registry.register(tool)
        if self.config.agent.enable_web_search:
            registry.register(
                WebSearchTool(
                    provider=self.config.agent.search.provider,
                    api_key_env=self.config.agent.search.api_key_env,
                    api_key=self.config.agent.search.api_key,
                )
            )
        return registry

    def _build_system_prompt(self, document_id: str, branch: Optional[str], style_template: Optional[str] = None) -> str:
        style = self.editor._load_style_template(style_template)
        habit_profile = self.editor._load_habit_profile()
        context = self.editor._load_conversation_context(document_id, branch)
        base = self.editor._build_system_prompt(style, habit_profile, context)
        return base + _AGENT_INSTRUCTIONS

    async def run(self, request: EditRequest) -> AsyncGenerator[dict, None]:
        """Run the agent loop, yielding event dicts.

        Event types: step / tool_call / tool_result / token / complete / error.
        """
        branch = request.branch or self.vcs.get_current_branch()
        try:
            original_content, branch = self.vcs.load_document(request.document_id, branch)
        except DocumentNotFoundError:
            # New document: the agent authors the full content via apply_edit.
            original_content = ""

        # Fallback: provider without tool-calling → single-shot edit path.
        if not self.llm.supports_tools():
            logger.info("Provider lacks tool support; falling back to single-shot edit")
            response = await self.editor.edit_document(request)
            yield {"type": "complete", "edit_response": response.model_dump()}
            return

        registry = self._build_registry(branch)
        system_prompt = self._build_system_prompt(request.document_id, branch, request.style_template)
        user_prompt = self.editor._build_user_prompt(
            original_content, request.instruction, request.selection
        )
        if not original_content:
            user_prompt += (
                f"\n\n注意：这是一篇新文档，目标文档 ID 为 `{request.document_id}`。"
                f"撰写完整内容后必须调用 apply_edit，且 document_id 必须精确使用 "
                f"`{request.document_id}`，不要自行改名。"
            )
        messages: list[ChatMessage] = [ChatMessage(role="user", content=user_prompt)]

        max_steps = self.config.agent.max_steps
        token_budget = self.config.agent.token_budget
        used_tokens = 0
        stop_reason: Optional[str] = None

        for step in range(1, max_steps + 1):
            yield {"type": "step", "step": step, "max_steps": max_steps}

            result = await self.llm.chat(
                messages,
                system=system_prompt,
                tools=registry.specs(),
                temperature=0.3,
            )
            used_tokens += int(result.usage.get("output_tokens", 0) or 0)

            if result.tool_calls:
                messages.append(
                    ChatMessage(
                        role="assistant",
                        content=result.text,
                        tool_calls=result.tool_calls,
                    )
                )
                for tc in result.tool_calls:
                    yield {
                        "type": "tool_call",
                        "id": tc.id,
                        "name": tc.name,
                        "arguments": tc.arguments,
                    }
                    tool_result = await registry.execute(tc.name, tc.arguments)
                    yield {
                        "type": "tool_result",
                        "id": tc.id,
                        "name": tc.name,
                        "result": tool_result,
                    }
                    messages.append(
                        ChatMessage(role="tool", content=tool_result, tool_call_id=tc.id)
                    )

                if token_budget and used_tokens >= token_budget:
                    stop_reason = "token_budget_exceeded"
                    yield {
                        "type": "error",
                        "message": f"token budget exceeded ({used_tokens}/{token_budget})",
                    }
                    break
                continue

            # No tool calls → final answer.
            if result.text:
                yield {"type": "token", "content": result.text}
            stop_reason = "done"
            break
        else:
            stop_reason = "max_steps_reached"
            yield {
                "type": "error",
                "message": f"reached max_steps ({max_steps}) without completion",
            }

        edited_doc_id = request.document_id
        edited_content = self.working_copy.get(request.document_id, original_content)
        if request.document_id not in self.working_copy and len(self.working_copy) == 1:
            # The model wrote to a single different doc id (e.g. it renamed a
            # new document); adopt that entry so the edit is not lost.
            edited_doc_id, edited_content = next(iter(self.working_copy.items()))
            logger.warning(
                "agent wrote to '%s' instead of requested '%s'; adopting it",
                edited_doc_id, request.document_id,
            )
        diff = self.editor._generate_diff(original_content, edited_content)
        yield {
            "type": "complete",
            "stop_reason": stop_reason,
            "edit_response": {
                "document_id": edited_doc_id,
                "original_content": original_content,
                "edited_content": edited_content,
                "diff_summary": diff.unified_diff,
                "branch": branch,
                "commit_hash": None,
            },
        }
