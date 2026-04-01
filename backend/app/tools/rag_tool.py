"""
RAG tool for document retrieval and question answering.
"""
from langchain.tools import BaseTool
from typing import Optional, Dict, Any, List
from pydantic import Field
import asyncio
import logging

logger = logging.getLogger(__name__)


def _format_results(results: List[Dict[str, Any]]) -> str:
    """Format search results into a readable string."""
    formatted_results = []
    sources = []

    for i, result in enumerate(results, 1):
        content = result["content"]
        score = result["score"]
        metadata = result.get("metadata", {})

        formatted_results.append(
            f"[Source {i}] (Relevance: {score:.2f})\n{content}"
        )
        source_name = metadata.get("source", f"Document {i}")
        sources.append(source_name)

    response = "\n\n".join(formatted_results)
    response += f"\n\nSources: {', '.join(set(sources))}"
    return response


class RAGTool(BaseTool):
    """Tool for retrieving information from uploaded documents."""
    
    name: str = "rag_tool"
    description: str = """Useful for retrieving information from uploaded documents and knowledge base.
    Input should be a question or query about the documents. Returns relevant information with sources."""
    
    rag_service: Any = Field(default=None, exclude=True)
    
    def _run(self, query: str) -> str:
        """Execute the RAG tool (sync — delegates to thread)."""
        try:
            results = self._sync_search(query)

            if not results:
                return "No relevant information found in the knowledge base."
            return _format_results(results)
        except Exception as e:
            logger.error(f"RAG tool error: {str(e)}")
            return f"Error retrieving information: {str(e)}"

    def _sync_search(self, query: str):
        """Perform a synchronous search using the async RAG service safely."""
        if self.rag_service is None:
            return []

        try:
            return asyncio.run(self.rag_service.search(query, top_k=5))
        except RuntimeError:
            # Fallback when asyncio.run cannot be used from an active event loop.
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(self.rag_service.search(query, top_k=5))
            finally:
                loop.close()
    
    async def _arun(self, query: str) -> str:
        """Async version of the RAG tool."""
        try:
            if self.rag_service is None:
                return "RAG service not available."
            results = await self.rag_service.search(query)
            
            if not results:
                return "No relevant information found in the knowledge base."
            return _format_results(results)
        except Exception as e:
            logger.error(f"RAG tool error: {str(e)}")
            return f"Error retrieving information: {str(e)}"
