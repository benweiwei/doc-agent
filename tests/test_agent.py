"""编辑 Agent 测试（Mock LLM 客户端）。"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from doc_agent.agent import DocumentEditor
from doc_agent.models import EditRequest


class TestDocumentEditor:
    """DocumentEditor 测试集。"""

    @pytest.fixture
    def editor(self, tmp_path, mock_llm_client):
        """创建 DocumentEditor，使用 mock LLM 和临时工作区。"""
        from doc_agent.config import AppConfig
        from doc_agent.vcs import VersionControl

        config = AppConfig(
            workspace={"path": str(tmp_path)},
            model={"provider": "cloud", "cloud": {"service": "anthropic", "model": "test", "api_key_env": "FAKE"}},
        )

        editor = DocumentEditor.__new__(DocumentEditor)
        editor.config = config
        editor.vcs = VersionControl(tmp_path)
        editor.vcs.init_workspace()
        editor.vcs.repo.config_writer().set_value("user", "name", "Test").release()
        editor.vcs.repo.config_writer().set_value("user", "email", "t@t.com").release()
        editor.llm = mock_llm_client
        editor.style_manager = MagicMock()
        editor.style_manager.get_template = MagicMock(return_value=None)
        return editor

    @pytest.mark.asyncio
    async def test_edit_document(self, editor):
        """完整编辑流程：mock LLM 返回编辑后内容。"""
        # 先保存一份原始文档
        editor.vcs.save_document("test.md", "# 原始标题\n\n原始内容", message="Init")

        request = EditRequest(
            document_id="test.md",
            instruction="将标题改为新标题",
        )

        response = await editor.edit_document(request)
        assert response.document_id == "test.md"
        assert response.original_content == "# 原始标题\n\n原始内容"
        assert response.edited_content == "编辑后的内容"
        assert response.branch == "main"
        assert response.commit_hash is None  # 未自动提交

    @pytest.mark.asyncio
    async def test_edit_with_selection(self, editor):
        """部分选中编辑。"""
        editor.vcs.save_document("test.md", "# Title\n\nParagraph 1\n\nParagraph 2\n", message="Init")

        request = EditRequest(
            document_id="test.md",
            instruction="将选中部分翻译为中文",
            selection="Paragraph 1",
        )

        response = await editor.edit_document(request)
        # 验证 LLM 被调用时 prompt 包含 selection 信息
        call_kwargs = editor.llm.generate.call_args
        prompt = call_kwargs.kwargs.get("prompt") or call_kwargs.args[0]
        assert "Paragraph 1" in prompt

    def test_build_system_prompt(self, editor):
        """系统提示构建正确。"""
        prompt = editor._build_system_prompt(style_template=None, habit_profile=None)
        assert "文档编辑助手" in prompt
        assert "编辑规则" in prompt

        # 带风格模板
        prompt_with_style = editor._build_system_prompt(
            style_template="语气：正式\n用词：高级",
            habit_profile=None,
        )
        assert "风格约束" in prompt_with_style
        assert "语气：正式" in prompt_with_style

        # 带习惯画像
        prompt_with_habit = editor._build_system_prompt(
            style_template=None,
            habit_profile={"句式偏好": "短句", "段落长度": "100字"},
        )
        assert "行文习惯" in prompt_with_habit
        assert "句式偏好" in prompt_with_habit

    def test_build_user_prompt(self, editor):
        """用户提示构建正确。"""
        prompt = editor._build_user_prompt(
            document="# Hello\n\nWorld",
            instruction="改写标题",
            selection=None,
        )
        assert "# Hello" in prompt
        assert "改写标题" in prompt
        assert "原始文档" in prompt

        # 带选中区域
        prompt_sel = editor._build_user_prompt(
            document="# Hello\n\nWorld",
            instruction="翻译",
            selection="World",
        )
        assert "需要修改的部分" in prompt_sel
        assert "World" in prompt_sel

    def test_generate_diff(self, editor):
        """diff 生成正确统计增删。"""
        original = "Line 1\nLine 2\nLine 3\n"
        edited = "Line 1\nLine 2 modified\nLine 3\nLine 4\n"

        result = editor._generate_diff(original, edited)
        assert result.old_content == original
        assert result.new_content == edited
        assert result.unified_diff != ""
        assert result.stats["additions"] > 0
        assert result.stats["deletions"] > 0

    def test_post_process(self, editor):
        """去除代码块标记。"""
        raw = "```markdown\n# Hello\n\nWorld\n```"
        result = editor._post_process(raw, "md")
        assert "```" not in result
        assert "# Hello" in result

        # 去除前言
        raw_with_preamble = "以下是修改后的文档内容：\n# New Title\n\nContent"
        result2 = editor._post_process(raw_with_preamble, "md")
        assert "以下是" not in result2
        assert "# New Title" in result2

    @pytest.mark.asyncio
    async def test_commit_edit(self, editor):
        """提交后返回 commit hash。"""
        editor.vcs.save_document("test.md", "Original", message="Init")

        commit_hash = await editor.commit_edit(
            document_id="test.md",
            content="Edited content",
            branch="main",
            message="Apply edit",
        )
        assert commit_hash is not None
        assert len(commit_hash) == 40

        # 验证内容已更新
        content, _ = editor.vcs.load_document("test.md")
        assert content == "Edited content"

    @pytest.mark.asyncio
    async def test_resolve_merge_conflict(self, editor):
        """LLM 辅助合并。"""
        editor.llm.generate = AsyncMock(return_value="合并后的结果文档")

        result = await editor.resolve_merge_conflict(
            base="Original",
            ours="Our version",
            theirs="Their version",
            instruction="保留两边的修改",
        )
        assert result == "合并后的结果文档"

        # 验证 LLM 被正确调用
        call_kwargs = editor.llm.generate.call_args
        prompt = call_kwargs.kwargs.get("prompt") or call_kwargs.args[0]
        assert "Our version" in prompt
        assert "Their version" in prompt
        assert "保留两边的修改" in prompt
