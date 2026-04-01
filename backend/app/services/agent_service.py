"""
Agent service with LangChain integration.
"""
import asyncio
import logging
import re
import unicodedata
from datetime import datetime, timezone
from typing import AsyncIterator, List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
try:
    from langchain.agents import create_agent
    HAS_CREATE_AGENT = True
except ImportError:
    HAS_CREATE_AGENT = False
    from langchain.agents import AgentExecutor, create_openai_tools_agent
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
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
- Keep response style simple and assistant-like. Avoid unnecessary technical detail.
- Be concise but helpful.
- Response format: plain text only. Do not use markdown bold/italics, markdown links, or decorative sections.
- Do not include URLs, references, or a "Sources:" section unless the user explicitly asks for sources/links.
- Avoid generic closing phrases like "let me know if you need anything else" unless the user asks for follow-up."""

_MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
_URL_PATTERN = re.compile(r"https?://[^\s)>\],]+")

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
    "actual",
    "actualmente",
    "hoy",
    "ahora",
    "ultimo",
    "ultima",
    "reciente",
    "presidente",
    "primer ministro",
    "prime minister",
    "president",
    "election",
    "eleccion",
)

FACTUAL_QUESTION_PREFIXES = (
    "who", "what", "when", "where", "which", "how much", "how many",
    "quien", "que", "cuando", "donde", "cual", "cuanto", "cuantos",
)

RAG_OR_LOCAL_HINTS = (
    "document", "documento", "archivo", "pdf", "docx", "knowledge base", "rag",
    "este codigo", "this code", "mi archivo", "my file", "uploaded",
)

SOURCE_REQUEST_HINTS = (
    "source", "sources", "fuente", "fuentes", "link", "links", "url", "urls",
    "referencia", "referencias", "citation", "citations", "evidence",
)

CASUAL_CHAT_HINTS = (
    "hola", "hello", "hi", "thanks", "thank you", "gracias",
    "buenas", "que tal", "como estas", "how are you",
)

SUMMARY_REQUEST_HINTS = (
    "resume", "resumen", "resumime", "resumir", "summarize", "summary",
    "que dicen", "what do they say", "what they say", "sintesis", "synthesis",
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
            temperature=0.3,
            streaming=True
        )
        
        # Initialize tools (inject shared RAGService)
        rag_tool = RAGTool()
        if rag_service is not None:
            rag_tool.rag_service = rag_service
        
        self.web_search_tool = WebSearchTool()
        self.rag_service = rag_service

        self.tools = [
            CodeInterpreterTool(),
            self.web_search_tool,
            URLAnalyzerTool(),
            rag_tool,
        ]
        
        # Conversation history store  {conversation_id: [messages]}
        self._history: Dict[str, List] = {}

        if HAS_CREATE_AGENT:
            # LangChain API (newer versions)
            self.agent = create_agent(
                model=self.llm,
                tools=self.tools,
                system_prompt=SYSTEM_PROMPT
            )
            self.agent_executor = None
        else:
            # Legacy LangChain API fallback
            prompt = ChatPromptTemplate.from_messages([
                ("system", SYSTEM_PROMPT),
                MessagesPlaceholder(variable_name="chat_history", optional=True),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad")
            ])
            self.agent = create_openai_tools_agent(self.llm, self.tools, prompt)
            self.agent_executor = AgentExecutor(
                agent=self.agent,
                tools=self.tools,
                verbose=True,
                max_iterations=settings.agent_max_iterations,
                max_execution_time=settings.agent_timeout,
                handle_parsing_errors=True
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
        normalized = re.sub(r"(?m)^#{1,6}\s*", "", normalized)
        normalized = re.sub(r"(?im)^\s*fuentes\s*:", "Sources:", normalized)
        normalized = re.sub(r"(?im)^\s*sources?\s*:", "Sources:", normalized)

        sources_match = re.search(r"(?im)^\s*Sources:\s*", normalized)
        if sources_match:
            body = normalized[:sources_match.start()].strip()
            urls = self._extract_urls(normalized[sources_match.start():])
            if urls:
                normalized = f"{body}\n\nSources: {', '.join(urls)}" if body else f"Sources: {', '.join(urls)}"
            else:
                normalized = body

        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized.strip()

    def _extract_urls(self, text: str) -> List[str]:
        """Extract and deduplicate URLs while preserving original order."""
        urls = []
        seen = set()
        for match in _URL_PATTERN.findall(text or ""):
            clean = match.rstrip(".,;)")
            if clean and clean not in seen:
                seen.add(clean)
                urls.append(clean)
        return urls

    def _coerce_content_to_text(self, content: Any) -> str:
        """Convert provider-specific content payloads into plain text."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and "text" in item:
                    parts.append(str(item.get("text", "")))
            return "\n".join([p for p in parts if p]).strip()
        return str(content or "")

    def _get_uploaded_document_count(self) -> int:
        """Return total uploaded document count across primary and fallback stores."""
        if self.rag_service is None:
            return 0

        try:
            stats = self.rag_service.get_collection_stats()
            primary = int(stats.get("document_count", 0) or 0)
            fallback = int(stats.get("fallback_document_count", 0) or 0)
            return primary + fallback
        except Exception as exc:
            logger.warning(f"Could not read document stats: {exc}")
            return 0

    def _is_document_summary_request(self, message: str) -> bool:
        """Detect summary requests that should be answered from uploaded documents."""
        lowered = self._normalize_for_matching(message)
        asks_summary = any(hint in lowered for hint in SUMMARY_REQUEST_HINTS)
        if not asks_summary:
            return False

        mentions_docs = any(hint in lowered for hint in RAG_OR_LOCAL_HINTS)
        if mentions_docs:
            return True

        return self._get_uploaded_document_count() > 0

    def _user_wants_sources(self, message: str) -> bool:
        """Check if user explicitly requested links/sources/citations."""
        lowered = self._normalize_for_matching(message)
        return any(hint in lowered for hint in SOURCE_REQUEST_HINTS)

    def _finalize_response_text(self, message: str, response_text: str) -> str:
        """Apply final response shaping based on user preference for citations."""
        normalized = self._normalize_response_format(response_text)
        if self._user_wants_sources(message):
            return normalized

        without_sources = re.sub(r"(?ims)\n*\s*Sources:\s*.*$", "", normalized).strip()
        without_sources = re.sub(r"https?://\S+", "", without_sources)
        without_sources = re.sub(r"\s{2,}", " ", without_sources)
        without_sources = re.sub(r"\n{3,}", "\n\n", without_sources)
        return without_sources.strip()

    def _normalize_for_matching(self, text: str) -> str:
        """Lowercase text and remove accents for robust keyword matching."""
        normalized = unicodedata.normalize("NFKD", text or "")
        return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()

    def _is_latest_f1_winner_query(self, message: str) -> bool:
        """Detect requests like 'who won the latest F1 race' (English/Spanish)."""
        lowered = self._normalize_for_matching(message)

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

    async def _build_direct_f1_latest_response(self, message: str) -> Optional[Dict[str, Any]]:
        """Serve latest F1 winner using official race data before invoking the LLM."""
        if not self._is_latest_f1_winner_query(message):
            return None

        latest = await asyncio.to_thread(self.web_search_tool.get_latest_formula1_winner)
        if not latest:
            return None

        response_text = (
            f"La ultima carrera de F1 fue {latest['race_name']} ({latest['race_date']}). "
            f"El ganador fue {latest['winner']} con {latest['team']} en {latest['circuit']}.\n\n"
            f"Sources: {latest['source_url']}"
        )

        return {
            "response": self._normalize_response_format(response_text),
            "tool_calls": [
                {
                    "tool": "web_search",
                    "input": {"query": "latest F1 race winner"},
                    "output": (
                        f"{latest['race_name']} ({latest['race_date']}) | "
                        f"Winner: {latest['winner']} ({latest['team']}) | "
                        f"Circuit: {latest['circuit']} | URL: {latest['source_url']}"
                    )
                }
            ],
            "sources": [latest["source_url"]],
        }

    async def _build_document_summary_response(self, message: str) -> Optional[Dict[str, Any]]:
        """Build a deterministic summary from uploaded documents when requested."""
        if not self._is_document_summary_request(message):
            return None

        lowered = self._normalize_for_matching(message)
        prioritize_recent = any(token in lowered for token in ("subido", "subidos", "uploaded", "reciente", "ultim"))

        if self.rag_service is None:
            return {
                "response": "No tengo acceso al indice documental en este momento. Vuelve a intentar en unos segundos.",
                "tool_calls": [],
                "sources": [],
            }

        snapshots = await self.rag_service.get_documents_snapshot(max_items=40, max_chars_per_item=1100)
        if not snapshots:
            return {
                "response": "No encontre documentos con contenido util para resumir. Sube al menos un archivo con texto y te hago el resumen.",
                "tool_calls": [
                    {
                        "tool": "rag_tool",
                        "input": {"query": message},
                        "output": "No document snapshots available",
                    }
                ],
                "sources": [],
            }

        grouped: Dict[str, List[str]] = {}
        for item in snapshots:
            source = str(item.get("source") or item.get("metadata", {}).get("source") or "Documento")
            text = str(item.get("content", "")).strip()
            if not text:
                continue
            grouped.setdefault(source, [])
            if len(grouped[source]) < 2:
                grouped[source].append(text)

        if not grouped:
            return {
                "response": "Subi documentos, pero no logre extraer contenido textual para resumirlos. Prueba con archivos que tengan texto seleccionable.",
                "tool_calls": [
                    {
                        "tool": "rag_tool",
                        "input": {"query": message},
                        "output": "Document snapshots had no readable content",
                    }
                ],
                "sources": [],
            }

        context_blocks = []
        ordered_sources = list(grouped.keys())
        for source in ordered_sources[:10]:
            excerpts = grouped[source]
            joined = "\n---\n".join(excerpts)
            context_blocks.append(f"[Source: {source}]\n{joined}")

        context = "\n\n".join(context_blocks)
        summary_prompt = (
            "Eres un asistente que resume documentos subidos por el usuario. "
            "Usa solo la informacion del CONTEXTO DOCUMENTAL.\n"
            "Si algo no esta en el contexto, dilo claramente.\n"
            "Devuelve un resumen en espanol, claro y accionable, con 4 a 8 lineas maximo.\n"
            "No incluyas links ni seccion de fuentes salvo que el usuario lo pida.\n\n"
            + ("Prioriza informacion de los documentos mas recientes.\n\n" if prioritize_recent else "")
            + f"Solicitud del usuario:\n{message}\n\n"
            + f"CONTEXTO DOCUMENTAL:\n{context}"
        )

        llm_result = await self.llm.ainvoke([HumanMessage(content=summary_prompt)])
        summary_text = self._coerce_content_to_text(getattr(llm_result, "content", ""))

        return {
            "response": summary_text,
            "tool_calls": [
                {
                    "tool": "rag_tool",
                    "input": {"query": message},
                    "output": f"Used {len(snapshots)} chunks across {len(ordered_sources)} sources",
                }
            ],
            "sources": ordered_sources,
        }

    async def _build_web_grounded_response(self, message: str) -> Optional[Dict[str, Any]]:
        """Build response from fresh web search context to reduce stale factual answers."""
        if not self._needs_fresh_web_context(message):
            return None

        web_results = await asyncio.to_thread(self.web_search_tool._run, message)
        if not web_results:
            return None

        lowered = web_results.lower()
        if web_results.startswith("Error performing web search") or "no results found" in lowered:
            return None

        current_date_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        grounded_prompt = (
            "Eres un asistente factual. Responde solo con informacion soportada por el contexto web entregado.\n"
            "Si el contexto es insuficiente o conflictivo, dilo explicitamente y evita afirmar datos no confirmados.\n"
            "Da una respuesta corta (2 a 5 lineas), clara y sin links, salvo que el usuario los pida.\n"
            f"Fecha UTC actual: {current_date_utc}.\n\n"
            f"Pregunta del usuario:\n{message}\n\n"
            f"CONTEXTO WEB:\n{web_results}"
        )

        llm_result = await self.llm.ainvoke([HumanMessage(content=grounded_prompt)])
        response_text = self._coerce_content_to_text(getattr(llm_result, "content", ""))
        sources = self._extract_urls(web_results)

        return {
            "response": response_text,
            "tool_calls": [
                {
                    "tool": "web_search",
                    "input": {"query": message},
                    "output": web_results[:1200],
                }
            ],
            "sources": sources,
        }

    def _needs_fresh_web_context(self, message: str) -> bool:
        """Detect whether a prompt likely needs live web data."""
        lowered = self._normalize_for_matching(message)

        if any(hint in lowered for hint in CASUAL_CHAT_HINTS):
            return False

        if any(hint in lowered for hint in RAG_OR_LOCAL_HINTS):
            return False

        if any(keyword in lowered for keyword in CURRENT_EVENTS_KEYWORDS):
            return True

        if "?" in message and len(lowered.split()) <= 24:
            return True

        if len(lowered.split()) <= 12:
            return True

        return any(lowered.startswith(prefix + " ") for prefix in FACTUAL_QUESTION_PREFIXES)

    async def _prepare_message(self, message: str) -> str:
        """Inject fresh web context for time-sensitive prompts."""
        current_date_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if not self._needs_fresh_web_context(message):
            return (
                f"Current UTC date: {current_date_utc}.\n"
                "Answer based on the current date context when relevant.\n\n"
                f"User message:\n{message}"
            )

        web_results = await asyncio.to_thread(self.web_search_tool._run, message)
        if web_results.startswith("Error performing web search"):
            logger.warning("Fresh web search failed, falling back to model/tool planning.")
            return (
                f"Current UTC date: {current_date_utc}.\n"
                "Web lookup failed; if the question needs fresh facts, say uncertainty and avoid stale claims.\n\n"
                f"User message:\n{message}"
            )

        return (
            f"Current UTC date: {current_date_utc}.\n"
            f"User message:\n{message}\n\n"
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

            direct_doc_response = await self._build_document_summary_response(message)
            if direct_doc_response is not None:
                final_response = self._finalize_response_text(message, direct_doc_response["response"])
                direct_doc_response["response"] = final_response
                if not self._user_wants_sources(message):
                    direct_doc_response["sources"] = []
                self._save_turn(conversation_id, message, final_response)
                return direct_doc_response

            direct_f1_response = await self._build_direct_f1_latest_response(message)
            if direct_f1_response is not None:
                final_response = self._finalize_response_text(message, direct_f1_response["response"])
                direct_f1_response["response"] = final_response
                if not self._user_wants_sources(message):
                    direct_f1_response["sources"] = []
                self._save_turn(conversation_id, message, final_response)
                return direct_f1_response

            direct_web_response = await self._build_web_grounded_response(message)
            if direct_web_response is not None:
                final_response = self._finalize_response_text(message, direct_web_response["response"])
                direct_web_response["response"] = final_response
                if not self._user_wants_sources(message):
                    direct_web_response["sources"] = []
                self._save_turn(conversation_id, message, final_response)
                return direct_web_response

            prepared_message = await self._prepare_message(message)

            if self.agent_executor is not None:
                result = await self.agent_executor.ainvoke({
                    "input": prepared_message,
                    "chat_history": history
                })
                response_text = str(result.get("output", ""))
            else:
                result = await self.agent.ainvoke({
                    "messages": [*history, HumanMessage(content=prepared_message)]
                })
                response_text = self._extract_response_text(result)

            response_text = self._finalize_response_text(message, response_text)
            self._save_turn(conversation_id, message, response_text)

            sources = self._extract_sources(result)
            if not self._user_wants_sources(message):
                sources = []

            return {
                "response": response_text,
                "tool_calls": self._extract_tool_calls(result),
                "sources": sources
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

            direct_doc_response = await self._build_document_summary_response(message)
            if direct_doc_response is not None:
                response_text = self._finalize_response_text(
                    message, str(direct_doc_response.get("response", ""))
                )
                self._save_turn(conversation_id, message, response_text)
                for token in response_text.split():
                    yield token + " "
                    await asyncio.sleep(0.02)
                return

            direct_f1_response = await self._build_direct_f1_latest_response(message)
            if direct_f1_response is not None:
                response_text = self._finalize_response_text(
                    message, str(direct_f1_response.get("response", ""))
                )
                self._save_turn(conversation_id, message, response_text)
                for token in response_text.split():
                    yield token + " "
                    await asyncio.sleep(0.02)
                return

            direct_web_response = await self._build_web_grounded_response(message)
            if direct_web_response is not None:
                response_text = self._finalize_response_text(
                    message, str(direct_web_response.get("response", ""))
                )
                self._save_turn(conversation_id, message, response_text)
                for token in response_text.split():
                    yield token + " "
                    await asyncio.sleep(0.02)
                return

            prepared_message = await self._prepare_message(message)

            if self.agent_executor is not None:
                result = await self.agent_executor.ainvoke({
                    "input": prepared_message,
                    "chat_history": history
                })
                response_text = str(result.get("output", ""))
            else:
                # LangChain v1 streaming events vary by provider/runtime, so we invoke
                # once and emit deterministic chunks for the WebSocket client.
                result = await self.agent.ainvoke({
                    "messages": [*history, HumanMessage(content=prepared_message)]
                })
                response_text = self._extract_response_text(result)

            response_text = self._finalize_response_text(message, response_text)

            self._save_turn(conversation_id, message, response_text)

            if not response_text:
                return

            for token in response_text.split():
                yield token + " "
                await asyncio.sleep(0.02)
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
