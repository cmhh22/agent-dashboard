"""
Tools API endpoints.
"""
from fastapi import APIRouter, HTTPException, Request
from app.models import ToolsResponse, ToolInfo
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=ToolsResponse)
async def get_tools(app_request: Request):
    """
    Get list of available agent tools.
    
    Returns:
        List of tools with descriptions and parameters
    """
    try:
        agent_service = app_request.app.state.agent_service
        tools_info = agent_service.get_tools_info()
        
        tools = [
            ToolInfo(
                name=tool["name"],
                description=tool["description"],
                parameters=tool["parameters"]
            )
            for tool in tools_info
        ]
        
        return ToolsResponse(
            tools=tools,
            count=len(tools)
        )
        
    except Exception as e:
        logger.error(f"Error getting tools: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve tools.")
