"""
WebSocket Routes — Real-time PA status and processing updates.
"""

import logging
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, channel: str):
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = []
        self.active_connections[channel].append(websocket)

    def disconnect(self, websocket: WebSocket, channel: str):
        if channel in self.active_connections:
            self.active_connections[channel].remove(websocket)

    async def broadcast(self, channel: str, message: dict):
        if channel in self.active_connections:
            for connection in self.active_connections[channel]:
                try:
                    await connection.send_json(message)
                except Exception:
                    pass


manager = ConnectionManager()


@router.websocket("/pa-status/{pa_id}")
async def pa_status_stream(websocket: WebSocket, pa_id: str):
    """Stream PA processing status updates in real-time."""
    await manager.connect(websocket, f"pa:{pa_id}")
    try:
        while True:
            data = await websocket.receive_text()
            # Handle client messages if needed
    except WebSocketDisconnect:
        manager.disconnect(websocket, f"pa:{pa_id}")


@router.websocket("/agent-status")
async def agent_status_stream(websocket: WebSocket):
    """Stream agent status updates for the dashboard."""
    await manager.connect(websocket, "agent-status")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, "agent-status")
