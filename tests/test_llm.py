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
