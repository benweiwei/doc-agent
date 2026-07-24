"""Web search tool with pluggable backends.

Default backend is DuckDuckGo (via the `ddgs` package, no API key required).
Optional `tavily` / `brave` / `bocha` backends read an API key from the configured
env var. Backend unavailability returns an error string to the model rather than
raising.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from doc_agent.tools.base import Tool

logger = logging.getLogger(__name__)


class WebSearchTool(Tool):
    name = "web_search"
    description = (
        "联网搜索资料，用于补充写作所需的事实、定义或最新信息。"
        "返回若干条标题、摘要和链接。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索查询"},
            "max_results": {
                "type": "integer",
                "description": "返回结果条数（默认 5，最多 10）",
            },
        },
        "required": ["query"],
    }

    def __init__(
        self,
        provider: str = "duckduckgo",
        api_key_env: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        self.provider = (provider or "duckduckgo").lower()
        self.api_key_env = api_key_env
        #: Direct API key (takes precedence over the env var).
        self._api_key = api_key

    def _resolve_key(self, default_env: str) -> str:
        """Resolve the API key: direct value first, else the configured env var."""
        if self._api_key:
            return self._api_key
        return os.environ.get(self.api_key_env or default_env, "")

    async def run(self, query: str = "", max_results: int = 5, **kwargs) -> str:
        if not query:
            return "Error: query is required"
        max_results = max(1, min(int(max_results or 5), 10))

        try:
            if self.provider == "duckduckgo":
                results = await self._search_duckduckgo(query, max_results)
            elif self.provider == "tavily":
                results = await self._search_tavily(query, max_results)
            elif self.provider == "brave":
                results = await self._search_brave(query, max_results)
            elif self.provider == "bocha":
                results = await self._search_bocha(query, max_results)
            else:
                return f"Error: unknown web search provider '{self.provider}'"
        except Exception as e:  # noqa: BLE001 - report to model instead of crashing
            logger.warning("web_search failed (%s): %s", self.provider, e)
            return f"Error: web search failed: {e}"

        if not results:
            return f"未搜索到 '{query}' 的相关结果。"

        lines = []
        for i, r in enumerate(results, start=1):
            title = r.get("title", "").strip()
            body = r.get("body", "").strip()
            url = r.get("url", "").strip()
            lines.append(f"{i}. {title}\n   {body}\n   {url}")
        return "\n".join(lines)

    # ─── Backends ────────────────────────────────────────────────────────────

    async def _search_duckduckgo(self, query: str, max_results: int) -> list[dict]:
        def _sync() -> list[dict]:
            try:
                from ddgs import DDGS  # type: ignore
            except ImportError:
                try:
                    from duckduckgo_search import DDGS  # type: ignore
                except ImportError as e:
                    raise RuntimeError(
                        "web search backend 'duckduckgo' requires the 'ddgs' package "
                        "(pip install ddgs)"
                    ) from e
            out: list[dict] = []
            with DDGS() as ddgs:
                for item in ddgs.text(query, max_results=max_results):
                    out.append(
                        {
                            "title": item.get("title", ""),
                            "body": item.get("body", ""),
                            "url": item.get("href", "") or item.get("url", ""),
                        }
                    )
            return out

        return await asyncio.to_thread(_sync)

    async def _search_tavily(self, query: str, max_results: int) -> list[dict]:
        import httpx

        api_key = self._resolve_key("TAVILY_API_KEY")
        if not api_key:
            raise RuntimeError("Tavily API key not configured")
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "max_results": max_results,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        return [
            {
                "title": r.get("title", ""),
                "body": r.get("content", ""),
                "url": r.get("url", ""),
            }
            for r in data.get("results", [])
        ]

    async def _search_brave(self, query: str, max_results: int) -> list[dict]:
        import httpx

        api_key = self._resolve_key("BRAVE_API_KEY")
        if not api_key:
            raise RuntimeError("Brave API key not configured")
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": max_results},
                headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
        return [
            {
                "title": r.get("title", ""),
                "body": r.get("description", ""),
                "url": r.get("url", ""),
            }
            for r in data.get("web", {}).get("results", [])
        ]

    async def _search_bocha(self, query: str, max_results: int) -> list[dict]:
        import httpx

        api_key = self._resolve_key("BOCHA_API_KEY")
        if not api_key:
            raise RuntimeError("Bocha API key not configured")
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.bochaai.com/v1/web-search",
                json={"query": query, "summary": True, "count": max_results},
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        pages = (data.get("data") or {}).get("webPages") or {}
        return [
            {
                "title": r.get("name", ""),
                "body": r.get("summary", "") or r.get("snippet", ""),
                "url": r.get("url", ""),
            }
            for r in pages.get("value", [])
        ]
