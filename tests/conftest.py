"""Shared fixtures for doc-agent tests."""

import subprocess

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def tmp_workspace(tmp_path):
    """创建临时 Git 工作区（已初始化的仓库）。"""
    from doc_agent.vcs import VersionControl

    vcs = VersionControl(tmp_path)
    vcs.init_workspace()
    # Configure git user for commits
    vcs.repo.config_writer().set_value("user", "name", "Test User").release()
    vcs.repo.config_writer().set_value("user", "email", "test@example.com").release()
    return vcs


@pytest.fixture
def mock_llm_client():
    """Mock LLM 客户端，generate 返回编辑后内容。"""
    client = AsyncMock()
    client.generate = AsyncMock(return_value="编辑后的内容")

    async def _mock_stream(*args, **kwargs):
        for token in ["编辑", "后的", "内容"]:
            yield token

    client.generate_stream = MagicMock(return_value=_mock_stream())
    client.is_available = MagicMock(return_value=True)
    return client


@pytest.fixture
def sample_config(tmp_path):
    """测试用 AppConfig，workspace 指向 tmp_path。"""
    from doc_agent.config import AppConfig

    return AppConfig(
        workspace={"path": str(tmp_path)},
        model={"provider": "cloud", "cloud": {"service": "anthropic", "model": "test-model", "api_key_env": "FAKE_KEY"}},
    )


@pytest.fixture
def sample_document_content():
    """示例文档内容。"""
    return "# 测试文档\n\n这是一个测试文档。\n\n## 第一节\n\n第一节的内容。\n"
