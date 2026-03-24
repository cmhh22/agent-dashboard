"""
Agent service with LangChain integration.
"""
import logging
from typing import AsyncIterator, List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage

from app.config import settings
from app.tools.code_interpreter_tool import CodeInterpreterTool
from app.tools.web_search_tool import get_search_tool
from app.tools.url_analyzer_tool import URLAnalyzerTool
from app.tools.rag_tool import RAGTool

logger = logging.getLogger(__name__)


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
        
        self.tools = [
            CodeInterpreterTool(),
            get_search_tool(),
            URLAnalyzerTool(),
            rag_tool,
        ]
        
        # Conversation history store  {conversation_id: [messages]}
        self._history: Dict[str, List] = {}
        
        # Create agent
        self.agent = self._create_agent()
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=True,
            max_iterations=settings.agent_max_iterations,
            max_execution_time=settings.agent_timeout,
            handle_parsing_errors=True
        )
        
        logger.info(f"Agent initialized with {len(self.tools)} tools")
    
    def _create_agent(self):
        """Create the LangChain agent with tools."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a powerful AI agent with access to advanced tools.
Use them proactively to give the best possible answer.

Available tools:
- Code Interpreter: Execute Python code for math, data analysis, algorithms, charts logic, string ops, date calculations — anything computable. Always use print() to show results.
- Web Search: Search the internet for current events, news, facts, documentation.
- URL Analyzer: Fetch and read the content of any URL the user shares or that you find via web search.
- RAG Knowledge Base: Search the user's uploaded documents for relevant information.

Guidelines:
- For math or calculations, use the Code Interpreter (write Python).
- When the user shares a URL, use URL Analyzer to read it.
- Cite sources when using RAG. Format your answers with clear structure.
- Be concise but thorough. Use markdown formatting in your responses."""),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])
        
        return create_openai_tools_agent(self.llm, self.tools, prompt)
    
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
            
            result = await self.agent_executor.ainvoke({
                "input": message,
                "chat_history": history
            })
            
            response_text = result["output"]
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
            collected = []
            
            async for chunk in self.agent_executor.astream({
                "input": message,
                "chat_history": history
            }):
                if "output" in chunk:
                    collected.append(chunk["output"])
                    yield chunk["output"]
                elif "actions" in chunk:
                    for action in chunk["actions"]:
                        yield f"\n[Using tool: {action.tool}]\n"
            
            # Save completed response to history
            self._save_turn(conversation_id, message, "".join(collected))
        except Exception as e:
            logger.error(f"Error streaming response: {str(e)}")
            raise
    
    def _extract_tool_calls(self, result: Dict) -> List[Dict[str, Any]]:
        """Extract tool calls from agent result."""
        tool_calls = []
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
