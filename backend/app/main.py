"""
Main FastAPI application entry point.
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.config import settings
from app.api import chat, documents, metrics, tools
from app.services.rag_service import RAGService
from app.services.agent_service import AgentService
from app.websocket.connection_manager import ConnectionManager

# Configure logging
logging.basicConfig(
    level=settings.log_level.upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    logger.info("Starting Agent Dashboard Backend...")
    
    # Initialize services — share RAGService with AgentService
    rag_service = RAGService()
    app.state.rag_service = rag_service
    app.state.agent_service = AgentService(rag_service=rag_service)
    app.state.connection_manager = ConnectionManager()
    
    logger.info("Services initialized successfully")
    yield
    
    # Cleanup
    logger.info("Shutting down Agent Dashboard Backend...")


# Create FastAPI app
app = FastAPI(
    title="Agent Dashboard API",
    description="FastAPI backend with LangChain Agent and RAG",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])
app.include_router(tools.router, prefix="/api/tools", tags=["tools"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Agent Dashboard API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time chat streaming."""
    await websocket.accept()
    connection_manager: ConnectionManager = app.state.connection_manager
    agent_service: AgentService = app.state.agent_service
    
    connection_id = await connection_manager.connect(websocket)
    logger.info(f"WebSocket client connected: {connection_id}")
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            message = data.get("message", "")
            
            if not message:
                await websocket.send_json({
                    "type": "error",
                    "content": "Empty message received"
                })
                continue
            
            # Process message with agent and stream response
            async for chunk in agent_service.stream_response(message):
                await websocket.send_json({
                    "type": "stream",
                    "content": chunk
                })
            
            # Send completion signal
            await websocket.send_json({
                "type": "complete",
                "content": ""
            })
            
    except WebSocketDisconnect:
        connection_manager.disconnect(connection_id)
        logger.info(f"WebSocket client disconnected: {connection_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        try:
            await websocket.send_json({
                "type": "error",
                "content": "An internal error occurred."
            })
        except Exception:
            pass  # Client already disconnected
        connection_manager.disconnect(connection_id)
