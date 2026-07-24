"""Document editing agent core logic."""

from __future__ import annotations

import difflib
import json
import logging
import re
from pathlib import Path
from typing import AsyncGenerator, Optional

from doc_agent.config import AppConfig
from doc_agent.llm import create_client
from doc_agent.models import DiffResult, EditRequest, EditResponse
from doc_agent.style.template import StyleManager
from doc_agent.vcs import VersionControl

logger = logging.getLogger(__name__)


class DocumentEditor:
    """文档编辑 Agent 核心。

    完整流程：加载文档 → 构建 Prompt → 调用 LLM → 后处理 → 生成 diff → 返回结果。
    """

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.vcs = VersionControl(Path(config.workspace.path).expanduser())
        self.llm = create_client(config.model)
        self.style_manager = StyleManager()

    # ─── Public API ───────────────────────────────────────────────────────────

    async def edit_document(self, request: EditRequest) -> EditResponse:
        """完整编辑流程：加载→构建Prompt→调用LLM→生成diff→返回结果（不自动提交）。

        Args:
            request: 编辑请求，包含文档ID、编辑指令等。

        Returns:
            EditResponse 包含原文、编辑后内容、diff摘要等。
        """
        # 1. 加载文档
        branch = request.branch or self.vcs.get_current_branch()
        content, branch = self.vcs.load_document(request.document_id, branch)

        # 2. 构建 prompts
        style_template = self._load_style_template(request.style_template)
        habit_profile = self._load_habit_profile()
        context = self._load_conversation_context(request.document_id, branch)
        system_prompt = self._build_system_prompt(style_template, habit_profile, context)
        user_prompt = self._build_user_prompt(content, request.instruction, request.selection)

        # 3. 调用 LLM
        raw_output = await self.llm.generate(
            prompt=user_prompt,
            system=system_prompt,
            temperature=0.3,
        )

        # 4. 后处理
        edited_content = self._post_process(raw_output, self._detect_format(request.document_id))

        # 5. 生成 diff
        diff_result = self._generate_diff(content, edited_content)

        return EditResponse(
            document_id=request.document_id,
            original_content=content,
            edited_content=edited_content,
            diff_summary=diff_result.unified_diff,
            branch=branch,
            commit_hash=None,
        )

    async def edit_document_stream(self, request: EditRequest) -> AsyncGenerator[str, None]:
        """流式编辑，逐段 yield 编辑后的内容。

        Args:
            request: 编辑请求。

        Yields:
            LLM 生成的文本片段（token）。
        """
        # 1. 加载文档
        branch = request.branch or self.vcs.get_current_branch()
        content, branch = self.vcs.load_document(request.document_id, branch)

        # 2. 构建 prompts
        style_template = self._load_style_template(request.style_template)
        habit_profile = self._load_habit_profile()
        context = self._load_conversation_context(request.document_id, branch)
        system_prompt = self._build_system_prompt(style_template, habit_profile, context)
        user_prompt = self._build_user_prompt(content, request.instruction, request.selection)

        # 3. 流式调用 LLM
        async for token in self.llm.generate_stream(
            prompt=user_prompt,
            system=system_prompt,
            temperature=0.3,
        ):
            yield token

    async def commit_edit(
        self,
        document_id: str,
        content: str,
        branch: Optional[str] = None,
        message: Optional[str] = None,
    ) -> str:
        """用户确认后提交编辑结果。

        Args:
            document_id: 文档ID（文件路径）。
            content: 编辑后的文档内容。
            branch: 目标分支，默认当前分支。
            message: 提交消息，默认自动生成。

        Returns:
            commit hash 字符串。
        """
        commit_message = message or f"doc-agent: edit {document_id}"
        commit_hash = self.vcs.save_document(
            doc_id=document_id,
            content=content,
            message=commit_message,
            branch=branch,
        )
        logger.info(
            "Committed edit for '%s' on branch '%s': %s",
            document_id,
            branch or self.vcs.get_current_branch(),
            commit_hash[:8],
        )
        return commit_hash

    # ─── Merge Conflict Resolution ────────────────────────────────────────────

    async def resolve_merge_conflict(
        self, base: str, ours: str, theirs: str, instruction: str = ""
    ) -> str:
        """使用 LLM 辅助解决合并冲突。

        Args:
            base: 共同祖先版本内容。
            ours: 当前分支版本内容。
            theirs: 要合并的分支版本内容。
            instruction: 用户的合并偏好指令（可选）。

        Returns:
            合并后的文档内容。
        """
        system_prompt = (
            "你是文档合并专家。你的任务是将两个分支对同一文档的不同修改智能合并为一个版本。\n\n"
            "## 合并规则\n"
            "- 尽可能保留两边的有效修改\n"
            "- 如果两边修改了同一段落的不同部分，合并两者\n"
            "- 如果两边修改了同一段落的相同内容且语义冲突，根据用户指令决定保留哪个\n"
            "- 保持文档格式一致\n"
            "- 只输出合并后的完整文档内容，不要添加任何解释"
        )

        user_parts = [
            "## 共同祖先版本（base）",
            "```",
            base or "（空文档）",
            "```",
            "",
            "## 当前分支版本（ours）",
            "```",
            ours or "（空文档）",
            "```",
            "",
            "## 要合并的分支版本（theirs）",
            "```",
            theirs or "（空文档）",
            "```",
        ]

        if instruction:
            user_parts.append("")
            user_parts.append("## 用户合并偏好")
            user_parts.append(instruction)

        user_parts.append("")
        user_parts.append("请输出合并后的完整文档内容：")

        user_prompt = "\n".join(user_parts)

        raw_output = await self.llm.generate(
            prompt=user_prompt,
            system=system_prompt,
            temperature=0.2,
        )

        # 后处理：去除可能的代码块包裹
        merged = self._post_process(raw_output, "md")
        return merged

    # ─── Conversation Context ───────────────────────────────────────────────

    def _load_conversation_context(self, document_id: str, branch: Optional[str] = None, limit: int = 5) -> str:
        """加载文档的对话历史上下文（按 branch 隔离）。"""
        interactions_file = Path(self.vcs.workspace_path) / ".doc-agent" / "interactions.json"
        if not interactions_file.exists():
            return ""

        try:
            data = json.loads(interactions_file.read_text(encoding="utf-8"))
            interactions = data.get("interactions", [])
            doc_interactions = [
                r for r in interactions
                if (r.get("document_id") == document_id or r.get("documentId") == document_id)
                and r.get("status") == "completed"
                and (branch is None or r.get("branch") == branch)
            ]
            doc_interactions = doc_interactions[-limit:]

            if not doc_interactions:
                return ""

            context_parts = []
            for r in doc_interactions:
                timestamp = r.get("timestamp", "")
                instruction = r.get("instruction", "")
                result = r.get("resultSummary") or r.get("result_summary") or r.get("editedContent") or r.get("edited_content") or ""
                if len(result) > 300:
                    result = result[:300] + "..."
                context_parts.append(f"### 用户指令 ({timestamp}):\n{instruction}\n\n### AI结果:\n{result}")

            return "\n\n---\n\n".join(context_parts)
        except Exception as e:
            logger.warning("加载对话上下文失败: %s", e)
            return ""

    # ─── Prompt Construction ──────────────────────────────────────────────────

    def _build_system_prompt(
        self,
        style_template: Optional[str] = None,
        habit_profile: Optional[dict] = None,
        context: str = "",
    ) -> str:
        """构建 system prompt：角色定义 + 风格约束 + 习惯画像。

        Args:
            style_template: 风格模板内容（如有）。
            habit_profile: 习惯画像字典（如有）。

        Returns:
            完整的 system prompt 字符串。
        """
        parts = [
            "你是一个专业的文档编辑助手。你的任务是根据用户的编辑指令修改文档内容。",
            "",
            "## 编辑规则",
            "- 只输出修改后的完整文档内容，不要添加任何解释或前缀",
            "- 保持文档原有的格式（Markdown/纯文本等）",
            "- 只修改与指令相关的部分，其他内容保持不变",
            "- 如果用户指定了选中文本，只修改选中部分并输出完整文档",
        ]

        if style_template:
            parts.append("")
            parts.append("## 风格约束")
            parts.append(style_template)

        if habit_profile:
            parts.append("")
            parts.append("## 行文习惯")
            habit_lines = []
            for key, value in habit_profile.items():
                habit_lines.append(f"- {key}: {value}")
            parts.append("\n".join(habit_lines))

        prompt = "\n".join(parts)

        if context:
            prompt += f"\n\n## Conversation History\n\n{context}\n\n请参考以上对话历史，保持编辑的连贯性和一致性。"

        return prompt

    def _build_user_prompt(
        self,
        document: str,
        instruction: str,
        selection: Optional[str] = None,
    ) -> str:
        """构建 user prompt：原文 + 编辑指令 + 选中区域。

        Args:
            document: 原始文档内容。
            instruction: 编辑指令。
            selection: 选中的文本片段（可选）。

        Returns:
            完整的 user prompt 字符串。
        """
        parts = [
            "## 原始文档",
            document,
            "",
            "## 编辑指令",
            instruction,
        ]

        if selection:
            parts.append("")
            parts.append("## 需要修改的部分")
            parts.append(selection)

        parts.append("")
        parts.append("请输出修改后的完整文档内容：")

        return "\n".join(parts)

    # ─── Diff Generation ──────────────────────────────────────────────────────

    def _generate_diff(self, original: str, edited: str) -> DiffResult:
        """生成 unified diff 和变更统计。

        Args:
            original: 原始内容。
            edited: 编辑后内容。

        Returns:
            DiffResult 包含 unified diff 文本和统计信息。
        """
        original_lines = original.splitlines(keepends=True)
        edited_lines = edited.splitlines(keepends=True)

        diff_lines = list(difflib.unified_diff(
            original_lines,
            edited_lines,
            fromfile="original",
            tofile="edited",
            lineterm="",
        ))

        unified_diff = "\n".join(diff_lines)

        # 统计增删行数
        additions = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
        deletions = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))

        return DiffResult(
            old_content=original,
            new_content=edited,
            unified_diff=unified_diff,
            stats={
                "additions": additions,
                "deletions": deletions,
                "total_changes": additions + deletions,
            },
        )

    # ─── Post Processing ──────────────────────────────────────────────────────

    def _post_process(self, raw_output: str, original_format: str) -> str:
        """后处理：清理多余标记、格式修正。

        去除 LLM 可能添加的 markdown 代码块标记、多余的前言后语。

        Args:
            raw_output: LLM 原始输出。
            original_format: 原始文档格式（md/txt/rst）。

        Returns:
            清理后的文档内容。
        """
        text = raw_output.strip()

        # 去除包裹整个输出的 ```markdown ... ``` 或 ```txt ... ``` 代码块
        # 匹配开头的 ```xxx 和结尾的 ```
        pattern = r"^```(?:markdown|md|text|txt|rst|plain)?\s*\n(.*?)```\s*$"
        match = re.match(pattern, text, re.DOTALL)
        if match:
            text = match.group(1)

        # 去除 LLM 可能添加的前言（如 "以下是修改后的文档：" "Here is the edited document:"）
        preamble_patterns = [
            r"^(?:以下是|这是|下面是).*?(?:内容|文档|结果)[:：]\s*\n",
            r"^(?:Here is|Below is|The following is).*?:\s*\n",
        ]
        for p in preamble_patterns:
            text = re.sub(p, "", text, count=1, flags=re.IGNORECASE)

        # 去除末尾的后语（如 "以上是修改后的内容。"）
        epilogue_patterns = [
            r"\n(?:以上是|这就是).*?(?:内容|文档|结果)[。.]\s*$",
            r"\n(?:I hope|Let me know|Please let).*$",
        ]
        for p in epilogue_patterns:
            text = re.sub(p, "", text, count=1, flags=re.IGNORECASE)

        return text.strip()

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _load_style_template(self, template_name: Optional[str] = None) -> Optional[str]:
        """加载风格模板内容。

        优先使用请求中指定的模板，其次使用配置默认模板。

        Args:
            template_name: 模板名称（可选）。

        Returns:
            模板内容字符串，或 None。
        """
        name = template_name or self.config.style.default_template
        if not name:
            return None

        content = self.style_manager.get_template(name)
        return content if content else None

    def _load_habit_profile(self) -> Optional[dict]:
        """加载习惯画像文件。

        优先使用 config.style.habit_profile 指定的路径；未配置时回退到
        “学习风格”默认保存位置 ~/.doc-agent/habit_profile.json，使学到的
        个人风格在 Agent / 单发模式下都能自动注入。

        Returns:
            习惯画像字典，或 None。
        """
        habit_path = self.config.style.habit_profile
        if habit_path:
            path = Path(habit_path).expanduser()
            if not path.is_absolute():
                # 相对于 workspace 目录
                path = Path(self.config.workspace.path).expanduser() / path
        else:
            # 回退到 HabitAnalyzer 的默认保存位置
            path = Path.home() / ".doc-agent" / "habit_profile.json"

        if not path.exists():
            return None

        try:
            content = path.read_text(encoding="utf-8")
            return json.loads(content)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load habit profile from '%s': %s", path, e)
            return None

    def _detect_format(self, doc_id: str) -> str:
        """根据文件扩展名检测文档格式。

        Args:
            doc_id: 文档文件路径。

        Returns:
            格式字符串：md / txt / rst。
        """
        suffix = Path(doc_id).suffix.lower()
        format_map = {
            ".md": "md",
            ".markdown": "md",
            ".txt": "txt",
            ".text": "txt",
            ".rst": "rst",
        }
        return format_map.get(suffix, "txt")
