"""Anonymous Parallel Search MCP client using the official HTTP transport."""
import asyncio
import json
import logging
from urllib.parse import urlsplit

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import TextContent

logger = logging.getLogger(__name__)

MCP_URL = "https://search.parallel.ai/mcp"
USER_AGENT = "AgentDashboard/1.0 (+https://github.com/cmhh22/agent-dashboard)"


def _format_search_text(text: str) -> str:
    """Convert the MCP's JSON source list to the existing plain-text contract."""
    try:
        payload = json.loads(text)
    except ValueError:
        return text.strip()
    if not isinstance(payload, dict) or "results" not in payload:
        return text.strip()

    formatted = []
    seen = set()
    for source in payload["results"]:
        url = source["url"]
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc or url in seen:
            continue
        seen.add(url)
        excerpts = "\n   ".join(source.get("excerpts") or [])
        title = source.get("title") or "No title"
        formatted.append(f"{len(formatted) + 1}. {title}\n   {excerpts}\n   URL: {url}")
    return "\n\n".join(formatted)


async def search(query: str, *, timeout: float) -> str:
    """Return source excerpts, or the tool's existing error/no-results contract.

    The deadline covers connection, initialization and the tool call. Cancellation
    propagates through the async transport, closing its streams and HTTP client.
    """
    if not query.strip():
        return "No results found for your query."

    try:
        async with asyncio.timeout(timeout):
            async with httpx.AsyncClient(
                headers={"User-Agent": USER_AGENT},
                timeout=httpx.Timeout(timeout),
                follow_redirects=True,
            ) as client:
                async with streamable_http_client(MCP_URL, http_client=client) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(
                            "web_search",
                            {"objective": query, "search_queries": [query]},
                        )
                        if result.isError:
                            return "Error performing web search: Parallel search is unavailable."
                        text = "\n\n".join(
                            _format_search_text(block.text) for block in result.content
                            if isinstance(block, TextContent)
                        ).strip()
                        return text or "No results found for your query."
    except TimeoutError:
        return "Error performing web search: Parallel search timed out."
    except Exception as exc:
        # Do not expose server payloads or transport diagnostics in the chat.
        logger.warning("Parallel search failed (%s)", type(exc).__name__)
        return "Error performing web search: Parallel search is unavailable."
