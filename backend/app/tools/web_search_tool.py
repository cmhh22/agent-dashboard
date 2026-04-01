"""
Web search tool using DuckDuckGo.
"""
from langchain.tools import BaseTool
from typing import List, Dict, Any, Optional
from ddgs import DDGS
import asyncio
import logging
import requests
import unicodedata
from datetime import datetime, timezone

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

    def _normalize_text(self, text: str) -> str:
        """Lowercase and strip accents for intent matching."""
        normalized = unicodedata.normalize("NFKD", text or "")
        return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()

    def _is_latest_f1_winner_query(self, query: str) -> bool:
        """Detect direct requests about the latest F1 race winner."""
        lowered = self._normalize_text(query)
        f1_markers = ("formula 1", "formula1", "f1", "grand prix")
        latest_markers = (
            "latest", "last", "most recent", "current", "ultimo", "ultima", "reciente"
        )
        winner_markers = ("winner", "won", "who won", "gano", "ganador", "gano la")

        return (
            any(marker in lowered for marker in f1_markers)
            and any(marker in lowered for marker in latest_markers)
            and any(marker in lowered for marker in winner_markers)
        )

    def get_latest_formula1_winner(self) -> Optional[Dict[str, str]]:
        """Fetch latest F1 race winner from official Ergast-compatible API endpoints."""
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

                return {
                    "race_name": race.get("raceName", "Latest Formula 1 Race"),
                    "race_date": race.get("date", "Unknown Date"),
                    "circuit": race.get("Circuit", {}).get("circuitName", "Unknown Circuit"),
                    "winner": full_name,
                    "team": constructor.get("name", "Unknown Team"),
                    "source_url": endpoint,
                }
            except Exception as exc:
                logger.debug(f"F1 data fetch failed for endpoint '{endpoint}': {exc}")

        return None

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

    def _is_freshness_sensitive_query(self, query: str) -> bool:
        """Detect queries where recency should be prioritized."""
        lowered = self._normalize_text(query)
        freshness_markers = (
            "latest", "current", "today", "yesterday", "now", "recent",
            "actual", "actualmente", "hoy", "ahora", "ultimo", "ultima", "reciente"
        )
        return any(marker in lowered for marker in freshness_markers)

    def _rank_results_by_recency(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Move likely newer references to the top based on year/date hints."""
        if not results:
            return results

        current_year = datetime.now(timezone.utc).year
        current_year_str = str(current_year)
        previous_year_str = str(current_year - 1)

        def rank(result: Dict[str, Any]) -> int:
            haystack = f"{result.get('title', '')} {result.get('body', '')}".lower()
            if current_year_str in haystack:
                return 0
            if previous_year_str in haystack:
                return 1
            if "today" in haystack or "hoy" in haystack:
                return 2
            if "yesterday" in haystack or "ayer" in haystack:
                return 3
            return 4

        return sorted(results, key=rank)

    def _formula1_latest_fallback(self) -> str:
        """Fallback source for latest F1 race result when web search returns nothing."""
        latest = self.get_latest_formula1_winner()
        if latest:
            return (
                f"1. {latest['race_name']} ({latest['race_date']})\n"
                f"   Winner: {latest['winner']} ({latest['team']})\n"
                f"   Circuit: {latest['circuit']}\n"
                f"   URL: {latest['source_url']}"
            )

        return ""
    
    def _run(self, query: str) -> str:
        """Execute the web search tool."""
        try:
            lowered = query.lower()
            freshness_sensitive = self._is_freshness_sensitive_query(query)
            current_year = datetime.now(timezone.utc).year

            if self._is_latest_f1_winner_query(query):
                latest = self.get_latest_formula1_winner()
                if latest:
                    return (
                        f"1. {latest['race_name']} ({latest['race_date']})\n"
                        f"   Winner: {latest['winner']} ({latest['team']})\n"
                        f"   Circuit: {latest['circuit']}\n"
                        f"   URL: {latest['source_url']}"
                    )

            with DDGS() as ddgs:
                candidate_queries = [query]
                if freshness_sensitive:
                    candidate_queries.insert(0, f"{query} {current_year}")
                if "latest" not in lowered and "current" not in lowered:
                    candidate_queries.append(f"latest {query}")
                if "result" not in lowered and "winner" not in lowered:
                    candidate_queries.append(f"{query} results")

                results: List[Dict[str, Any]] = []

                if freshness_sensitive:
                    news_queries = [f"{query} {current_year}", query]
                    for news_query in news_queries:
                        try:
                            results = list(ddgs.news(news_query, max_results=_DEFAULT_MAX_RESULTS))
                            if results:
                                break
                        except Exception as exc:
                            logger.debug(f"DDG news attempt failed for query '{news_query}': {exc}")

                for candidate in candidate_queries:
                    if results:
                        break
                    results = self._text_search_with_fallbacks(ddgs, candidate)
                    if results:
                        break

                if not results:
                    try:
                        results = list(ddgs.news(query, max_results=_DEFAULT_MAX_RESULTS))
                    except Exception as exc:
                        logger.debug(f"DDG news fallback failed for query '{query}': {exc}")

            results = self._rank_results_by_recency(results)

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
