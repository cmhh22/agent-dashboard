"""
Chat API endpoints.
"""
from fastapi import APIRouter, HTTPException, Request
from app.models import ChatRequest, ChatResponse
import uuid
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest, app_request: Request):
    """
    Process a chat message with the agent.
    
    Args:
        request: Chat request with user message
        app_request: FastAPI request object for accessing app state
        
    Returns:
        Agent response with metadata
    """
    try:
        agent_service = app_request.app.state.agent_service
        
        # Generate conversation ID if not provided
        conversation_id = request.conversation_id or str(uuid.uuid4())
        
        # Process message with agent
        result = await agent_service.process_message(
            request.message, conversation_id=conversation_id
        )
        
        return ChatResponse(
            response=result["response"],
            conversation_id=conversation_id,
            tool_calls=result.get("tool_calls"),
            sources=result.get("sources")
        )
        
    except Exception as e:
        logger.error(f"Error processing chat: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process chat message.")
