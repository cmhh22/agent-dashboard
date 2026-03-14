"""
WebSocket connection manager for handling multiple client connections.
"""
from fastapi import WebSocket
from typing import Dict
import uuid
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manage WebSocket connections."""
    
    def __init__(self):
        """Initialize the connection manager."""
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket) -> str:
        """
        Accept a new WebSocket connection.
        
        Args:
            websocket: WebSocket connection
            
        Returns:
            Connection ID
        """
        connection_id = str(uuid.uuid4())
        self.active_connections[connection_id] = websocket
        logger.info(f"New connection: {connection_id}")
        return connection_id
    
    def disconnect(self, connection_id: str):
        """
        Remove a WebSocket connection.
        
        Args:
            connection_id: Connection ID to remove
        """
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
            logger.info(f"Connection closed: {connection_id}")
    
    async def send_personal_message(self, message: dict, connection_id: str):
        """
        Send a message to a specific connection.
        
        Args:
            message: Message to send
            connection_id: Target connection ID
        """
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            await websocket.send_json(message)
    
    async def broadcast(self, message: dict):
        """
        Broadcast a message to all connections.
        
        Args:
            message: Message to broadcast
        """
        disconnected = []
        for connection_id, websocket in list(self.active_connections.items()):
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to {connection_id}: {str(e)}")
                disconnected.append(connection_id)
        # Clean up dead connections
        for cid in disconnected:
            self.disconnect(cid)
    
    def get_connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self.active_connections)
