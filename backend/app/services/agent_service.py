"""
Agent service with LangChain integration.
"""
import asyncio
import logging
import re
from typing import AsyncIterator, List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from app.config import settings
from app.tools.code_interpreter_tool import CodeInterpreterTool
from app.tools.web_search_tool import WebSearchTool
from app.tools.url_analyzer_tool import URLAnalyzerTool
from app.tools.rag_tool import RAGTool

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a powerful AI agent with access to advanced tools.
Use them proactively to give the best possible answer.

Available tools:
- Code Interpreter: Execute Python code for math, data analysis, algorithms, charts logic, string ops, date calculations — anything computable. Always use print() to show results.
- Web Search: Search the internet (via DuckDuckGo) for current events, news, facts, documentation.
- URL Analyzer: Fetch and read the content of any URL the user shares or that you find via web search.
- RAG Knowledge Base: Search the user's uploaded documents for relevant information.

Guidelines:
- For math or calculations, use the Code Interpreter (write Python).
- For current events or time-sensitive facts (sports results, race winners, market moves, breaking news), use Web Search before answering.
- When the user shares a URL, use URL Analyzer to read it.
- Cite sources when using RAG. Format your answers with clear structure.
- Be concise but thorough.
- Response format: plain text only. Do not use markdown bold/italics, markdown links, or decorative sections.
- Put the direct answer first, then optionally add a single line that starts with "Sources:" followed by URLs.
- Avoid generic closing phrases like "let me know if you need anything else" unless the user asks for follow-up."""

_MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")

CURRENT_EVENTS_KEYWORDS = (
    "latest",
    "current",
    "today",
    "yesterday",
    "this week",
    "news",
    "who won",
    "winner",
    "champion",
    "race",
    "grand prix",
    "formula 1",
    "f1",
    "score",
    "result",
    "standings",
    "price",
    "market",
)


class AgentService:
    """Service for managing LangChain agent operations."""
    
    def __init__(self, rag_service=None):
        """Initialize the agent service.
        
        Args:
            rag_service: Optional shared RAGService instance to inject into RAGTool.
        """
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            temperature=0.7,
            streaming=True
        )
        
        # Initialize tools (inject shared RAGService)
        rag_tool = RAGTool()
        if rag_service is not None:
            rag_tool.rag_service = rag_service
        
        self.web_search_tool = WebSearchTool()

        self.tools = [
            CodeInterpreterTool(),
            self.web_search_tool,
            URLAnalyzerTool(),
            rag_tool,
        ]
        
        # Conversation history store  {conversation_id: [messages]}
        self._history: Dict[str, List] = {}

        # Create LangChain v1 agent graph
        self.agent = create_agent(
            model=self.llm,
            tools=self.tools,
            system_prompt=SYSTEM_PROMPT
        )
        
        logger.info(f"Agent initialized with {len(self.tools)} tools")
    
    def _get_history(self, conversation_id: Optional[str] = None) -> List:
        """Get chat history for a conversation."""
        if not conversation_id:
            return []
        return self._history.get(conversation_id, [])
    
    def _save_turn(self, conversation_id: Optional[str], user_msg: str, ai_msg: str):
        """Save a conversation turn to history."""
        if not conversation_id:
            return
        history = self._history.setdefault(conversation_id, [])
        history.append(HumanMessage(content=user_msg))
        history.append(AIMessage(content=ai_msg))
        # Keep last 20 messages to prevent unbounded growth
        if len(history) > 20:
            self._history[conversation_id] = history[-20:]

    def _normalize_response_format(self, response_text: str) -> str:
        """Normalize model output to clean plain text for the frontend."""
        if not response_text:
            return response_text

        normalized = response_text.replace("**", "")
        normalized = normalized.replace("__", "")
        normalized = normalized.replace("```", "")
        normalized = _MARKDOWN_LINK_PATTERN.sub(r"\1: \2", normalized)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized.strip()

    def _needs_fresh_web_context(self, message: str) -> bool:
        """Detect whether a prompt likely needs live web data."""
        lowered = message.lower()
        return any(keyword in lowered for keyword in CURRENT_EVENTS_KEYWORDS)

    async def _prepare_message(self, message: str) -> str:
        """Inject fresh web context for time-sensitive prompts."""
        if not self._needs_fresh_web_context(message):
            return message

        web_results = await asyncio.to_thread(self.web_search_tool._run, message)
        if web_results.startswith("Error performing web search"):
            logger.warning("Fresh web search failed, falling back to model/tool planning.")
            return message

        return (
            f"{message}\n\n"
            "Fresh web search context (prioritize this for timely facts and cite URLs):\n"
            f"{web_results}\n\n"
            "If sources conflict or look outdated, clearly state uncertainty."
        )
    
    async def process_message(
        self, message: str, chat_history: List = None, conversation_id: str = None
    ) -> Dict[str, Any]:
        """
        Process a message with the agent.
        
        Args:
            message: User message
            chat_history: Optional explicit chat history
            conversation_id: Optional conversation ID for stored history
            
        Returns:
            Agent response with metadata
        """
        try:
            history = chat_history or self._get_history(conversation_id)
            prepared_message = await self._prepare_message(message)

            result = await self.agent.ainvoke({
                "messages": [*history, HumanMessage(content=prepared_message)]
            })

            response_text = self._extract_response_text(result)
            response_text = self._normalize_response_format(response_text)
            self._save_turn(conversation_id, message, response_text)

            return {
                "response": response_text,
                "tool_calls": self._extract_tool_calls(result),
                "sources": self._extract_sources(result)
            }
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            raise
    
    async def stream_response(
        self, message: str, chat_history: List = None, conversation_id: str = None
    ) -> AsyncIterator[str]:
        """
        Stream agent response token by token.
        
        Args:
            message: User message
            chat_history: Optional chat history
            conversation_id: Optional conversation ID for stored history
            
        Yields:
            Response tokens
        """
        try:
            history = chat_history or self._get_history(conversation_id)
            prepared_message = await self._prepare_message(message)

            # LangChain v1 streaming events vary by provider/runtime, so we invoke
            # once and emit deterministic chunks for the WebSocket client.
            result = await self.agent.ainvoke({
                "messages": [*history, HumanMessage(content=prepared_message)]
            })
            response_text = self._extract_response_text(result)
            response_text = self._normalize_response_format(response_text)

            self._save_turn(conversation_id, message, response_text)

            if not response_text:
                return

            for token in response_text.split():
                yield token + " "
                await asyncio.sleep(0)
        except Exception as e:
            logger.error(f"Error streaming response: {str(e)}")
            raise

    def _extract_response_text(self, result: Dict[str, Any]) -> str:
        """Extract the final assistant text from a LangChain v1 agent result."""
        messages = result.get("messages", []) if isinstance(result, dict) else []
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                content = msg.content
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    parts = []
                    for item in content:
                        if isinstance(item, str):
                            parts.append(item)
                        elif isinstance(item, dict) and "text" in item:
                            parts.append(str(item["text"]))
                    return "\n".join([p for p in parts if p]).strip()
                return str(content)
        return ""
    
    def _extract_tool_calls(self, result: Dict) -> List[Dict[str, Any]]:
        """Extract tool calls from agent result."""
        tool_calls = []
        if not isinstance(result, dict):
            return tool_calls

        messages = result.get("messages", [])
        if messages:
            tool_outputs: Dict[str, str] = {}

            for msg in messages:
                if isinstance(msg, ToolMessage):
                    tool_outputs[msg.tool_call_id] = str(msg.content)

            for msg in messages:
                if isinstance(msg, AIMessage):
                    for call in msg.tool_calls:
                        tool_id = call.get("id", "")
                        tool_calls.append({
                            "tool": call.get("name", "unknown_tool"),
                            "input": call.get("args", {}),
                            "output": tool_outputs.get(tool_id, "")
                        })
            return tool_calls

        # Backward-compatible extraction for older result format
        if "intermediate_steps" in result:
            for step in result["intermediate_steps"]:
                if len(step) >= 2:
                    action, observation = step[0], step[1]
                    tool_calls.append({
                        "tool": action.tool,
                        "input": action.tool_input,
                        "output": str(observation)
                    })
        return tool_calls
    
    def _extract_sources(self, result: Dict) -> List[str]:
        """Extract RAG sources from agent result."""
        sources = []
        tool_calls = self._extract_tool_calls(result)
        for call in tool_calls:
            if call.get("tool") == "rag_tool":
                output = str(call.get("output", ""))
                marker = "Sources:"
                if marker in output:
                    tail = output.split(marker, 1)[1].strip()
                    parsed = [s.strip() for s in tail.split(",") if s.strip()]
                    sources.extend(parsed)

        if "intermediate_steps" in result:
            for step in result["intermediate_steps"]:
                if len(step) >= 2:
                    action = step[0]
                    if action.tool == "rag_tool":
                        observation = step[1]
                        if isinstance(observation, dict) and "sources" in observation:
                            sources.extend(observation["sources"])
        return sources
    
    def get_tools_info(self) -> List[Dict[str, Any]]:
        """Get information about available tools."""
        tools_info = []
        for tool in self.tools:
            schema = getattr(tool, "args_schema", None)
            if schema is not None:
                try:
                    params = schema.schema() if hasattr(schema, 'schema') else {}
                except Exception:
                    params = {}
            else:
                params = {}
            tools_info.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": params
            })
        return tools_info
