"""
Web search tool supporting DuckDuckGo and Tavily providers.
"""
from langchain.tools import BaseTool
from typing import Optional, ClassVar
from duckduckgo_search import DDGS
import asyncio
import logging

from app.config import settings

logger = logging.getLogger(__name__)

# Max results at module level
_DEFAULT_MAX_RESULTS = 5


class WebSearchTool(BaseTool):
    """Tool for searching the web using DuckDuckGo."""

    name: str = "web_search"
    description: str = """Useful for searching the internet for current information, news, facts, or any topic.
    Input should be a search query string. Returns relevant search results with titles and snippets."""

    def _run(self, query: str) -> str:
        """Execute the web search tool."""
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=_DEFAULT_MAX_RESULTS))

            if not results:
                return "No results found for your query."

            # Format results
            formatted_results = []
            for i, result in enumerate(results, 1):
                title = result.get('title', 'No title')
                snippet = result.get('body', 'No description')
                url = result.get('href', '')
                formatted_results.append(
                    f"{i}. {title}\n   {snippet}\n   URL: {url}"
                )

            return "\n\n".join(formatted_results)

        except Exception as e:
            logger.error(f"Web search error: {str(e)}")
            return f"Error performing web search: {str(e)}"

    async def _arun(self, query: str) -> str:
        """Async version of the web search tool."""
        return await asyncio.to_thread(self._run, query)


class TavilySearchTool(BaseTool):
    """Tool for searching the web using Tavily."""

    name: str = "web_search"
    description: str = """Useful for searching the internet for current information, news, facts, or any topic.
    Input should be a search query string. Returns relevant search results with titles and snippets."""

    def _run(self, query: str) -> str:
        """Execute the web search tool using Tavily."""
        try:
            from tavily import TavilyClient

            client = TavilyClient(api_key=settings.tavily_api_key)
            response = client.search(
                query=query,
                max_results=_DEFAULT_MAX_RESULTS,
                search_depth="basic",
            )

            results = response.get("results", [])
            if not results:
                return "No results found for your query."

            formatted_results = []
            for i, result in enumerate(results, 1):
                title = result.get("title", "No title")
                snippet = result.get("content", "No description")
                url = result.get("url", "")
                formatted_results.append(
                    f"{i}. {title}\n   {snippet}\n   URL: {url}"
                )

            return "\n\n".join(formatted_results)

        except Exception as e:
            logger.error(f"Tavily search error: {str(e)}")
            return f"Error performing web search: {str(e)}"

    async def _arun(self, query: str) -> str:
        """Async version of the Tavily search tool."""
        return await asyncio.to_thread(self._run, query)


def get_search_tool() -> BaseTool:
    """Factory function that returns the configured search tool.

    Returns TavilySearchTool when SEARCH_PROVIDER=tavily,
    otherwise returns the default DuckDuckGo WebSearchTool.
    """
    provider = settings.search_provider.lower()
    if provider == "tavily":
        logger.info("Using Tavily as the web search provider")
        return TavilySearchTool()
    logger.info("Using DuckDuckGo as the web search provider")
    return WebSearchTool()
