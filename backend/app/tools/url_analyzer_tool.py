"""
URL Analyzer tool — fetches a webpage and returns a concise summary of its content.
"""
import asyncio
import logging
import re
from typing import Optional
from langchain.tools import BaseTool

logger = logging.getLogger(__name__)

_TIMEOUT = 15
_MAX_CONTENT = 6000  # chars to send back


def _clean_html(html: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    # Remove script/style blocks
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.S | re.I)
    # Remove tags
    text = re.sub(r"<[^>]+>", " ", html)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


class URLAnalyzerTool(BaseTool):
    """Fetch a URL and return its text content."""

    name: str = "url_analyzer"
    description: str = (
        "Fetch any URL / webpage and return its text content for analysis. "
        "Useful for reading articles, docs, or any web page the user shares. "
        "Input should be a valid URL starting with http:// or https://."
    )

    def _run(self, url: str) -> str:
        """Synchronous fetch."""
        import requests
        url = url.strip().strip("\"'")
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; AgentDashboard/1.0)"
            }
            resp = requests.get(url, headers=headers, timeout=_TIMEOUT, allow_redirects=True)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            if "text/html" in content_type:
                text = _clean_html(resp.text)
            else:
                text = resp.text

            truncated = text[:_MAX_CONTENT]
            if len(text) > _MAX_CONTENT:
                truncated += "\n\n[... content truncated ...]"

            return f"📄 Content from {url}:\n\n{truncated}"

        except requests.exceptions.Timeout:
            return f"⏱️ Timed out fetching {url}"
        except requests.exceptions.HTTPError as e:
            return f"❌ HTTP error {e.response.status_code} fetching {url}"
        except Exception as e:
            logger.error(f"URL analyzer error: {e}")
            return f"Error fetching URL: {str(e)}"

    async def _arun(self, url: str) -> str:
        return await asyncio.to_thread(self._run, url)
