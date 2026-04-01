"""
Web search tool using DuckDuckGo.
"""
from langchain.tools import BaseTool
from typing import List, Dict, Any
from ddgs import DDGS
import asyncio
import logging
import requests

logger = logging.getLogger(__name__)

# Max results at module level
_DEFAULT_MAX_RESULTS = 5


class WebSearchTool(BaseTool):
    """Tool for searching the web using DuckDuckGo."""
    
    name: str = "web_search"
    description: str = """Useful for searching the internet for current information, news, facts, or any topic.
    Input should be a search query string. Returns relevant search results with titles and snippets."""

    def _text_search_with_fallbacks(self, ddgs: DDGS, query: str) -> List[Dict[str, Any]]:
        """Run DuckDuckGo text search with multiple backend strategies."""
        attempts = [
            {},
            {"backend": "html"},
            {"backend": "lite"},
        ]

        for attempt in attempts:
            try:
                results = list(ddgs.text(query, max_results=_DEFAULT_MAX_RESULTS, **attempt))
                if results:
                    return results
            except TypeError:
                # Some duckduckgo-search versions may not support the backend kwarg.
                continue
            except Exception as exc:
                logger.debug(f"DDG text search attempt failed for query '{query}': {exc}")

        return []

    def _normalize_results(self, results: List[Dict[str, Any]]) -> str:
        """Format and deduplicate search results for LLM consumption."""
        if not results:
            return "No results found for your query."

        formatted_results = []
        seen_urls = set()

        for i, result in enumerate(results, 1):
            title = result.get('title', 'No title')
            snippet = result.get('body', 'No description')
            url = result.get('href') or result.get('url') or ''
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)

            formatted_results.append(
                f"{i}. {title}\n   {snippet}\n   URL: {url}"
            )

        return "\n\n".join(formatted_results) if formatted_results else "No results found for your query."

    def _formula1_latest_fallback(self) -> str:
        """Fallback source for latest F1 race result when web search returns nothing."""
        endpoints = [
            "https://api.jolpi.ca/ergast/f1/current/last/results.json",
            "https://ergast.com/api/f1/current/last/results.json",
        ]

        for endpoint in endpoints:
            try:
                response = requests.get(endpoint, timeout=10)
                if response.status_code != 200:
                    continue

                payload = response.json()
                races = payload.get("MRData", {}).get("RaceTable", {}).get("Races", [])
                if not races:
                    continue

                race = races[0]
                results = race.get("Results", [])
                if not results:
                    continue

                winner = results[0]
                driver = winner.get("Driver", {})
                constructor = winner.get("Constructor", {})

                given = driver.get("givenName", "")
                family = driver.get("familyName", "")
                full_name = f"{given} {family}".strip() or "Unknown Driver"
                team_name = constructor.get("name", "Unknown Team")

                race_name = race.get("raceName", "Latest Formula 1 Race")
                race_date = race.get("date", "Unknown Date")
                circuit = race.get("Circuit", {}).get("circuitName", "Unknown Circuit")

                return (
                    f"1. {race_name} ({race_date})\n"
                    f"   Winner: {full_name} ({team_name})\n"
                    f"   Circuit: {circuit}\n"
                    f"   URL: {endpoint}"
                )
            except Exception as exc:
                logger.debug(f"F1 fallback failed for endpoint '{endpoint}': {exc}")

        return ""
    
    def _run(self, query: str) -> str:
        """Execute the web search tool."""
        try:
            lowered = query.lower()
            with DDGS() as ddgs:
                candidate_queries = [query]
                if "latest" not in lowered and "current" not in lowered:
                    candidate_queries.append(f"latest {query}")
                if "result" not in lowered and "winner" not in lowered:
                    candidate_queries.append(f"{query} results")

                results: List[Dict[str, Any]] = []
                for candidate in candidate_queries:
                    results = self._text_search_with_fallbacks(ddgs, candidate)
                    if results:
                        break

                if not results:
                    try:
                        results = list(ddgs.news(query, max_results=_DEFAULT_MAX_RESULTS))
                    except Exception as exc:
                        logger.debug(f"DDG news fallback failed for query '{query}': {exc}")

            if not results and ("formula 1" in lowered or "f1" in lowered or "grand prix" in lowered):
                f1_fallback = self._formula1_latest_fallback()
                if f1_fallback:
                    return f1_fallback

            return self._normalize_results(results)
            
        except Exception as e:
            logger.error(f"Web search error: {str(e)}")
            return f"Error performing web search: {str(e)}"
    
    async def _arun(self, query: str) -> str:
        """Async version of the web search tool."""
        return await asyncio.to_thread(self._run, query)
