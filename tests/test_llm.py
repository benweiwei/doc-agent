"""LLM 适配器测试（mock，不实际调用 API）。"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from doc_agent.config import ModelConfig
from doc_agent.llm import (
    HybridClient,
    LLMTimeoutError,
    create_client,
)


class TestCreateClient:
    """create_client 工厂函数测试。"""

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test-key"})
    def test_create_client_anthropic(self):
        """创建 Anthropic 客户端。"""
        config = ModelConfig(
            provider="cloud",
            cloud={"service": "anthropic", "model": "claude-sonnet-4-20250514", "api_key_env": "ANTHROPIC_API_KEY"},
        )
        client = create_client(config)
        from doc_agent.llm.anthropic_client import AnthropicClient
        assert isinstance(client, AnthropicClient)
        assert client.model == "claude-sonnet-4-20250514"

    @patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key"})
    def test_create_client_openai(self):
        """创建 OpenAI 客户端。"""
        config = ModelConfig(
            provider="cloud",
            cloud={"service": "openai", "model": "gpt-4o", "api_key_env": "OPENAI_API_KEY"},
        )
        client = create_client(config)
        from doc_agent.llm.openai_client import OpenAIClient
        assert isinstance(client, OpenAIClient)
        assert client.model == "gpt-4o"

    def test_create_client_ollama(self):
        """创建 Ollama 客户端。"""
        config = ModelConfig(
            provider="local",
            local={"service": "ollama", "model": "llama3", "endpoint": "http://localhost:11434"},
        )
        client = create_client(config)
        from doc_agent.llm.ollama_client import OllamaClient
        assert isinstance(client, OllamaClient)
        assert client.model == "llama3"


class TestHybridClient:
    """HybridClient 降级测试。"""

    @pytest.mark.asyncio
    async def test_hybrid_client_primary_success(self):
        """主模型成功直接返回。"""
        primary = AsyncMock()
        primary.generate = AsyncMock(return_value="Primary response")
        primary.is_available = MagicMock(return_value=True)

        fallback = AsyncMock()
        fallback.generate = AsyncMock(return_value="Fallback response")
        fallback.is_available = MagicMock(return_value=True)

        client = HybridClient(primary=primary, fallback=fallback)
        result = await client.generate("Hello")

        assert result == "Primary response"
        primary.generate.assert_called_once()
        fallback.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_hybrid_client_fallback(self):
        """主模型失败降级到备选。"""
        from doc_agent.llm import LLMError

        primary = AsyncMock()
        primary.generate = AsyncMock(side_effect=LLMError("Primary failed", provider="test"))
        primary.is_available = MagicMock(return_value=True)

        fallback = AsyncMock()
        fallback.generate = AsyncMock(return_value="Fallback response")
        fallback.is_available = MagicMock(return_value=True)

        client = HybridClient(primary=primary, fallback=fallback)
        result = await client.generate("Hello")

        assert result == "Fallback response"
        fallback.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self):
        """超时时重试。"""
        primary = AsyncMock()
        # 前两次超时，第三次成功
        primary.generate = AsyncMock(
            side_effect=[
                LLMTimeoutError("timeout", provider="test"),
                LLMTimeoutError("timeout", provider="test"),
                "Success after retry",
            ]
        )
        primary.is_available = MagicMock(return_value=True)

        client = HybridClient(primary=primary, fallback=None, max_retries=3)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client.generate("Hello")

        assert result == "Success after retry"
        assert primary.generate.call_count == 3

    @pytest.mark.asyncio
    async def test_generate_stream(self):
        """流式生成返回 AsyncGenerator。"""
        tokens = ["Hello", " ", "World"]

        async def _mock_stream(*args, **kwargs):
            for t in tokens:
                yield t

        primary = AsyncMock()
        primary.generate_stream = MagicMock(return_value=_mock_stream())
        primary.is_available = MagicMock(return_value=True)

        client = HybridClient(primary=primary, fallback=None)
        collected = []
        async for token in client.generate_stream("Hello"):
            collected.append(token)

        assert collected == tokens


class TestChatToolCalling:
    """chat() 工具调用：请求组装与响应解析（mock SDK）。"""

    @pytest.mark.asyncio
    async def test_anthropic_chat_parses_text_and_tool_use(self):
        from doc_agent.llm.anthropic_client import AnthropicClient
        from doc_agent.llm.base import ChatMessage, ToolSpec

        client = AnthropicClient(model="claude", api_key_env="X")
        assert client.supports_tools() is True

        text_block = MagicMock(type="text")
        text_block.text = "hello"
        tool_block = MagicMock(type="tool_use")
        tool_block.id = "t1"
        tool_block.name = "read_document"
        tool_block.input = {"document_id": "a.md"}
        resp = MagicMock()
        resp.content = [text_block, tool_block]
        resp.stop_reason = "tool_use"
        resp.usage = MagicMock(input_tokens=1, output_tokens=2)

        fake_client = MagicMock()
        fake_client.messages.create = AsyncMock(return_value=resp)
        client._client = fake_client

        result = await client.chat(
            [ChatMessage(role="user", content="hi")],
            tools=[ToolSpec(name="read_document", description="d", parameters={"type": "object"})],
        )

        assert result.text == "hello"
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "read_document"
        assert result.tool_calls[0].arguments == {"document_id": "a.md"}
        _, kwargs = fake_client.messages.create.call_args
        assert kwargs["tools"][0]["name"] == "read_document"
        assert "input_schema" in kwargs["tools"][0]

    @pytest.mark.asyncio
    async def test_openai_chat_parses_tool_calls(self):
        from doc_agent.llm.openai_client import OpenAIClient
        from doc_agent.llm.base import ChatMessage, ToolSpec

        client = OpenAIClient(model="gpt", api_key="k")
        assert client.supports_tools() is True

        func = MagicMock()
        func.name = "apply_edit"
        func.arguments = '{"document_id": "a.md", "new_content": "x"}'
        tc = MagicMock()
        tc.id = "t1"
        tc.function = func
        message = MagicMock()
        message.content = "ok"
        message.tool_calls = [tc]
        choice = MagicMock()
        choice.message = message
        choice.finish_reason = "tool_calls"
        resp = MagicMock()
        resp.choices = [choice]
        resp.usage = MagicMock(prompt_tokens=1, completion_tokens=2)

        fake_client = MagicMock()
        fake_client.chat.completions.create = AsyncMock(return_value=resp)
        client._client = fake_client

        result = await client.chat(
            [ChatMessage(role="user", content="hi")],
            tools=[ToolSpec(name="apply_edit", description="d", parameters={})],
        )

        assert result.text == "ok"
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "apply_edit"
        assert result.tool_calls[0].arguments["document_id"] == "a.md"
        _, kwargs = fake_client.chat.completions.create.call_args
        assert kwargs["tools"][0]["type"] == "function"
        assert kwargs["tools"][0]["function"]["name"] == "apply_edit"

    @pytest.mark.asyncio
    async def test_ollama_chat_raises(self):
        from doc_agent.llm import LLMError
        from doc_agent.llm.ollama_client import OllamaClient

        client = OllamaClient()
        assert client.supports_tools() is False
        with pytest.raises(LLMError):
            await client.chat([])
