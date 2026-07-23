"""LLM client implementations.

Provides factory function `create_client` and `HybridClient` for fallback.
"""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator, Optional

import structlog

from doc_agent.llm.base import (
    BaseLLMClient,
    LLMClient,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMUnavailableError,
)

logger = structlog.get_logger(__name__)

__all__ = [
    "BaseLLMClient",
    "LLMClient",
    "LLMError",
    "LLMTimeoutError",
    "LLMRateLimitError",
    "LLMUnavailableError",
    "HybridClient",
    "create_client",
]


# ─── Retryable check ──────────────────────────────────────────────────────────


def _is_retryable(error: Exception) -> bool:
    """Determine if an error is retryable (timeout, 5xx, rate limit)."""
    return isinstance(error, (LLMTimeoutError, LLMRateLimitError, LLMUnavailableError))


# ─── HybridClient ─────────────────────────────────────────────────────────────


class HybridClient(LLMClient):
    """混合客户端：支持 fallback 降级。

    Primary 失败时自动降级到 fallback，并使用指数退避重试。
    """

    def __init__(
        self,
        primary: LLMClient,
        fallback: Optional[LLMClient] = None,
        max_retries: int = 3,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.max_retries = max_retries

    def is_available(self) -> bool:
        """Check if at least one client is available."""
        if self.primary.is_available():
            return True
        if self.fallback is not None:
            return self.fallback.is_available()
        return False

    async def generate(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs,
    ) -> str:
        """Generate with retry and fallback."""
        # Try primary with exponential backoff
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                return await self.primary.generate(
                    prompt, system=system, max_tokens=max_tokens,
                    temperature=temperature, **kwargs,
                )
            except Exception as e:
                last_error = e
                if not _is_retryable(e):
                    logger.warning(
                        "hybrid.primary.non_retryable",
                        error=str(e),
                        attempt=attempt + 1,
                    )
                    break
                wait = 2**attempt  # 1s, 2s, 4s
                logger.warning(
                    "hybrid.primary.retry",
                    error=str(e),
                    attempt=attempt + 1,
                    wait_seconds=wait,
                )
                await asyncio.sleep(wait)

        # Try fallback
        if self.fallback is not None:
            logger.info("hybrid.fallback", reason=str(last_error))
            try:
                return await self.fallback.generate(
                    prompt, system=system, max_tokens=max_tokens,
                    temperature=temperature, **kwargs,
                )
            except Exception as fallback_error:
                logger.error("hybrid.fallback.failed", error=str(fallback_error))
                raise LLMError(
                    f"Both primary and fallback failed. "
                    f"Primary: {last_error}, Fallback: {fallback_error}",
                    provider="hybrid",
                ) from fallback_error

        # No fallback available
        if last_error is not None:
            raise last_error
        raise LLMError("No LLM client available", provider="hybrid")

    async def generate_stream(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Stream with retry and fallback."""
        # Try primary with exponential backoff
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                async for token in self.primary.generate_stream(
                    prompt, system=system, max_tokens=max_tokens,
                    temperature=temperature, **kwargs,
                ):
                    yield token
                return  # Success
            except Exception as e:
                last_error = e
                if not _is_retryable(e):
                    logger.warning(
                        "hybrid.stream.primary.non_retryable",
                        error=str(e),
                        attempt=attempt + 1,
                    )
                    break
                wait = 2**attempt
                logger.warning(
                    "hybrid.stream.primary.retry",
                    error=str(e),
                    attempt=attempt + 1,
                    wait_seconds=wait,
                )
                await asyncio.sleep(wait)

        # Try fallback
        if self.fallback is not None:
            logger.info("hybrid.stream.fallback", reason=str(last_error))
            try:
                async for token in self.fallback.generate_stream(
                    prompt, system=system, max_tokens=max_tokens,
                    temperature=temperature, **kwargs,
                ):
                    yield token
                return
            except Exception as fallback_error:
                logger.error("hybrid.stream.fallback.failed", error=str(fallback_error))
                raise LLMError(
                    f"Both primary and fallback failed. "
                    f"Primary: {last_error}, Fallback: {fallback_error}",
                    provider="hybrid",
                ) from fallback_error

        # No fallback available
        if last_error is not None:
            raise last_error
        raise LLMError("No LLM client available", provider="hybrid")


# ─── Factory Function ─────────────────────────────────────────────────────────


def _create_single_client(provider: str, config) -> LLMClient:
    """Create a single LLM client based on provider type."""
    if provider == "cloud":
        service = config.cloud.service
        if service == "anthropic":
            from doc_agent.llm.anthropic_client import AnthropicClient

            return AnthropicClient(
                model=config.cloud.model,
                api_key_env=config.cloud.api_key_env,
            )
        elif service == "openai":
            from doc_agent.llm.openai_client import OpenAIClient

            return OpenAIClient(
                model=config.cloud.model,
                api_key_env=config.cloud.api_key_env,
                api_key=config.cloud.api_key,
                base_url=config.cloud.base_url,
            )
        else:
            raise ValueError(f"Unsupported cloud service: {service}")
    elif provider == "local":
        from doc_agent.llm.ollama_client import OllamaClient

        return OllamaClient(
            model=config.local.model,
            endpoint=config.local.endpoint,
        )
    else:
        raise ValueError(f"Unsupported provider: {provider}")


def create_client(config) -> LLMClient:
    """根据配置创建 LLM 客户端实例。

    Args:
        config: ModelConfig instance from doc_agent.config.

    Returns:
        LLMClient instance (may be wrapped in HybridClient if fallback enabled).
    """
    from doc_agent.config import ModelConfig

    if not isinstance(config, ModelConfig):
        raise TypeError(f"Expected ModelConfig, got {type(config)}")

    primary = _create_single_client(config.provider, config)

    if not config.fallback:
        return primary

    # Build fallback: if primary is cloud, fallback to local; vice versa
    fallback_provider = "local" if config.provider == "cloud" else "cloud"
    try:
        fallback = _create_single_client(fallback_provider, config)
    except (ValueError, Exception) as e:
        logger.warning("hybrid.fallback_init_failed", error=str(e))
        fallback = None

    return HybridClient(primary=primary, fallback=fallback)
