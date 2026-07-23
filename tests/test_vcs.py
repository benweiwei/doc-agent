"""Git 版本控制测试。"""

import pytest
from pathlib import Path

from doc_agent.vcs import VersionControl, BRANCH_PREFIX


class TestVersionControl:
    """VersionControl 测试集。"""

    def test_init_workspace(self, tmp_workspace):
        """初始化仓库，检查 main 分支存在。"""
        vcs = tmp_workspace
        branches = [h.name for h in vcs.repo.heads]
        assert "main" in branches
        assert vcs.get_current_branch() == "main"

    def test_save_and_load_document(self, tmp_workspace):
        """保存文档后能正确加载。"""
        vcs = tmp_workspace
        content = "# Hello\n\nThis is a test document."
        commit_hash = vcs.save_document("test.md", content, message="Add test.md")

        assert commit_hash is not None
        assert len(commit_hash) == 40  # full sha

        loaded_content, branch = vcs.load_document("test.md")
        assert loaded_content == content
        assert branch == "main"

    def test_list_documents(self, tmp_workspace):
        """列出文档包含正确的文件。"""
        vcs = tmp_workspace
        vcs.save_document("doc1.md", "# Doc 1", message="Add doc1")
        vcs.save_document("doc2.txt", "Doc 2 content", message="Add doc2")
        vcs.save_document("notes/sub.rst", "Sub doc", message="Add sub")

        docs = vcs.list_documents()
        assert "doc1.md" in docs
        assert "doc2.txt" in docs
        assert "notes/sub.rst" in docs

    def test_create_branch(self, tmp_workspace):
        """创建分支后能在列表中看到。"""
        vcs = tmp_workspace
        vcs.create_branch("blog-version", delivery_target="博客读者")

        branch_names = [h.name for h in vcs.repo.heads]
        full_name = f"{BRANCH_PREFIX}blog-version"
        assert full_name in branch_names

    def test_switch_branch(self, tmp_workspace):
        """切换分支后当前分支正确。"""
        vcs = tmp_workspace
        vcs.create_branch("dev", delivery_target="开发团队")
        full_name = f"{BRANCH_PREFIX}dev"

        vcs.switch_branch(full_name)
        assert vcs.get_current_branch() == full_name

        vcs.switch_branch("main")
        assert vcs.get_current_branch() == "main"

    def test_save_to_branch(self, tmp_workspace):
        """在特定分支保存文档。"""
        vcs = tmp_workspace
        vcs.create_branch("feature", delivery_target="功能分支")
        full_name = f"{BRANCH_PREFIX}feature"

        # 在 feature 分支保存文档
        vcs.save_document("feature_doc.md", "# Feature", message="Add feature doc", branch=full_name)

        # 从 feature 分支加载
        content, branch = vcs.load_document("feature_doc.md", branch=full_name)
        assert content == "# Feature"
        assert branch == full_name

        # main 分支不应该有该文档
        from doc_agent.vcs import DocumentNotFoundError
        with pytest.raises(DocumentNotFoundError):
            vcs.load_document("feature_doc.md", branch="main")

    def test_get_history(self, tmp_workspace):
        """多次提交后历史记录正确。"""
        vcs = tmp_workspace
        vcs.save_document("doc.md", "Version 1", message="First version")
        vcs.save_document("doc.md", "Version 2", message="Second version")
        vcs.save_document("doc.md", "Version 3", message="Third version")

        history = vcs.get_history(doc_id="doc.md")
        assert len(history) >= 3
        # 最近的提交在前
        assert "Third version" in history[0]["message"]
        assert "Second version" in history[1]["message"]
        assert "First version" in history[2]["message"]
        # 每条记录都有必需字段
        for entry in history:
            assert "commit_hash" in entry
            assert "message" in entry
            assert "author" in entry
            assert "timestamp" in entry

    def test_get_diff(self, tmp_workspace):
        """修改文档后能获取 diff。"""
        vcs = tmp_workspace
        vcs.save_document("doc.md", "Line 1\nLine 2\n", message="Initial")
        commit_a = vcs.repo.head.commit.hexsha

        vcs.save_document("doc.md", "Line 1\nLine 2 modified\nLine 3\n", message="Modify")
        commit_b = vcs.repo.head.commit.hexsha

        diff = vcs.get_diff("doc.md", commit_a=commit_a, commit_b=commit_b)
        assert diff  # 非空
        assert "Line 2 modified" in diff or "+Line 2 modified" in diff

    def test_merge_no_conflict(self, tmp_workspace):
        """无冲突合并成功。"""
        vcs = tmp_workspace
        # 在 main 创建文档
        vcs.save_document("shared.md", "# Shared\n\nOriginal content.\n", message="Add shared.md")

        # 创建分支并在分支修改不同文件
        vcs.create_branch("merge-test", delivery_target="合并测试")
        full_name = f"{BRANCH_PREFIX}merge-test"
        vcs.save_document("branch_only.md", "# Branch Only", message="Add branch doc", branch=full_name)

        # 合并到 main
        result = vcs.merge_branches(full_name, "main")
        assert result["success"] is True
        assert result["conflicts"] == []
        assert result["merge_commit"] != ""

    def test_merge_with_conflict(self, tmp_workspace):
        """有冲突时返回冲突信息。"""
        vcs = tmp_workspace
        # 在 main 创建文档
        vcs.save_document("conflict.md", "Original line\n", message="Add conflict.md")

        # 创建分支
        vcs.create_branch("conflict-branch", delivery_target="冲突测试")
        full_name = f"{BRANCH_PREFIX}conflict-branch"

        # 在分支修改同一文件
        vcs.save_document("conflict.md", "Branch modified line\n", message="Branch edit", branch=full_name)

        # 在 main 修改同一文件
        vcs.save_document("conflict.md", "Main modified line\n", message="Main edit")

        # 尝试合并——应有冲突
        result = vcs.merge_branches(full_name, "main")
        assert result["success"] is False
        assert len(result["conflicts"]) > 0
        assert "conflict.md" in result["conflicts"]
