"""
Pydantic models for API requests and responses.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    message: str = Field(..., description="User message", min_length=1)
    conversation_id: Optional[str] = Field(None, description="Conversation ID for context")


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    response: str = Field(..., description="Agent response")
    conversation_id: str = Field(..., description="Conversation ID")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(default=None, description="Tools used by agent")
    sources: Optional[List[str]] = Field(default=None, description="RAG sources used")


class DocumentUpload(BaseModel):
    """Model for document upload."""
    content: str = Field(..., description="Document content")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Document metadata")


class DocumentResponse(BaseModel):
    """Response model for document operations."""
    document_id: str = Field(..., description="Document ID")
    status: str = Field(..., description="Operation status")
    message: str = Field(..., description="Status message")


class ToolInfo(BaseModel):
    """Information about an agent tool."""
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Tool parameters")


class ToolsResponse(BaseModel):
    """Response model for tools listing."""
    tools: List[ToolInfo] = Field(..., description="Available tools")
    count: int = Field(..., description="Number of tools")


class RAGMetrics(BaseModel):
    """RAG evaluation metrics."""
    faithfulness: float = Field(..., description="Faithfulness score", ge=0, le=1)
    answer_relevancy: float = Field(..., description="Answer relevancy score", ge=0, le=1)
    context_precision: float = Field(..., description="Context precision score", ge=0, le=1)
    context_recall: float = Field(..., description="Context recall score", ge=0, le=1)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MetricsResponse(BaseModel):
    """Response model for metrics endpoint."""
    metrics: RAGMetrics = Field(..., description="Current metrics")
    queries_processed: int = Field(..., description="Total queries processed")
    average_response_time: float = Field(..., description="Average response time in seconds")
