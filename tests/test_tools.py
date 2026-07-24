"""Tool system tests: registry dispatch and document/web tools."""

import pytest

from doc_agent.tools.base import Tool, ToolRegistry
from doc_agent.tools.document_tools import build_document_tools
from doc_agent.tools.web_search import WebSearchTool


class _EchoTool(Tool):
    name = "echo"
    description = "echo back"
    parameters = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    async def run(self, text: str = "") -> str:
        return f"echo:{text}"


class _BoomTool(Tool):
    name = "boom"
    description = "always fails"
    parameters = {"type": "object", "properties": {}}

    async def run(self, **kwargs) -> str:
        raise RuntimeError("kaboom")


class TestToolRegistry:
    @pytest.mark.asyncio
    async def test_register_and_execute(self):
        reg = ToolRegistry()
        reg.register(_EchoTool())
        assert len(reg) == 1
        assert reg.get("echo") is not None
        result = await reg.execute("echo", {"text": "hi"})
        assert result == "echo:hi"

    def test_specs_export(self):
        reg = ToolRegistry()
        reg.register(_EchoTool())
        specs = reg.specs()
        assert len(specs) == 1
        assert specs[0].name == "echo"
        assert "text" in specs[0].parameters["properties"]

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        reg = ToolRegistry()
        result = await reg.execute("nope", {})
        assert result.startswith("Error:")
        assert "unknown tool" in result

    @pytest.mark.asyncio
    async def test_execution_error_is_captured(self):
        reg = ToolRegistry()
        reg.register(_BoomTool())
        result = await reg.execute("boom", {})
        assert result.startswith("Error:")
        assert "kaboom" in result

    @pytest.mark.asyncio
    async def test_invalid_arguments_return_error(self):
        reg = ToolRegistry()
        reg.register(_EchoTool())
        result = await reg.execute("echo", {"unexpected": 1})
        assert result.startswith("Error:")


class TestDocumentTools:
    @pytest.fixture
    def workspace_with_docs(self, tmp_workspace):
        tmp_workspace.save_document("guide.md", "# Guide\n\napple banana\n", message="init")
        tmp_workspace.save_document("notes.md", "# Notes\n\ncherry\n", message="init")
        return tmp_workspace

    @pytest.mark.asyncio
    async def test_read_and_list(self, workspace_with_docs):
        wc: dict[str, str] = {}
        tools = {t.name: t for t in build_document_tools(workspace_with_docs, None, wc)}

        content = await tools["read_document"].run(document_id="guide.md")
        assert "apple banana" in content

        listing = await tools["list_documents"].run()
        assert "guide.md" in listing
        assert "notes.md" in listing

    @pytest.mark.asyncio
    async def test_search_documents(self, workspace_with_docs):
        wc: dict[str, str] = {}
        tools = {t.name: t for t in build_document_tools(workspace_with_docs, None, wc)}

        result = await tools["search_documents"].run(query="banana")
        assert "guide.md" in result
        assert "notes.md" not in result

        miss = await tools["search_documents"].run(query="zzz-not-there")
        assert "未找到" in miss

    @pytest.mark.asyncio
    async def test_apply_edit_only_mutates_working_copy(self, workspace_with_docs):
        wc: dict[str, str] = {}
        tools = {t.name: t for t in build_document_tools(workspace_with_docs, None, wc)}

        msg = await tools["apply_edit"].run(
            document_id="guide.md", new_content="# Guide\n\nNEW CONTENT\n"
        )
        assert "guide.md" in msg
        # working copy updated
        assert wc["guide.md"] == "# Guide\n\nNEW CONTENT\n"
        # read now reflects working copy
        read_back = await tools["read_document"].run(document_id="guide.md")
        assert "NEW CONTENT" in read_back
        # but committed VCS content is unchanged
        committed, _ = workspace_with_docs.load_document("guide.md", None)
        assert "NEW CONTENT" not in committed
        assert "apple banana" in committed

    @pytest.mark.asyncio
    async def test_read_missing_document(self, workspace_with_docs):
        wc: dict[str, str] = {}
        tools = {t.name: t for t in build_document_tools(workspace_with_docs, None, wc)}
        result = await tools["read_document"].run(document_id="missing.md")
        assert result.startswith("Error:")


class TestWebSearchTool:
    @pytest.mark.asyncio
    async def test_unknown_provider_returns_error(self):
        tool = WebSearchTool(provider="nonexistent")
        result = await tool.run(query="python")
        assert result.startswith("Error:")

    @pytest.mark.asyncio
    async def test_tavily_missing_key_returns_error(self, monkeypatch):
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        tool = WebSearchTool(provider="tavily")
        result = await tool.run(query="python")
        assert result.startswith("Error:")

    @pytest.mark.asyncio
    async def test_bocha_missing_key_returns_error(self, monkeypatch):
        monkeypatch.delenv("BOCHA_API_KEY", raising=False)
        tool = WebSearchTool(provider="bocha")
        result = await tool.run(query="python")
        assert result.startswith("Error:")

    @pytest.mark.asyncio
    async def test_empty_query_returns_error(self):
        tool = WebSearchTool(provider="duckduckgo")
        result = await tool.run(query="")
        assert result.startswith("Error:")
