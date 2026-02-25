"""
WebSocket connection manager for real-time notifications and team chat.
"""
import logging
import json
from typing import Dict, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections per user."""

    def __init__(self):
        # user_id -> set of WebSocket connections (supports multiple tabs/devices)
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        logger.info(f"WebSocket connected: user={user_id} (total={self.count_connections()})")

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        logger.info(f"WebSocket disconnected: user={user_id} (total={self.count_connections()})")

    def count_connections(self) -> int:
        return sum(len(conns) for conns in self.active_connections.values())

    def is_online(self, user_id: str) -> bool:
        return user_id in self.active_connections and len(self.active_connections[user_id]) > 0

    async def send_to_user(self, user_id: str, message: dict):
        """Send a message to all connections of a specific user."""
        if user_id not in self.active_connections:
            return
        dead = []
        for ws in self.active_connections[user_id]:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active_connections[user_id].discard(ws)

    async def send_to_users(self, user_ids: list, message: dict):
        """Send a message to multiple users."""
        for uid in user_ids:
            await self.send_to_user(uid, message)

    async def broadcast_all(self, message: dict):
        """Send to every connected user."""
        for user_id in list(self.active_connections.keys()):
            await self.send_to_user(user_id, message)


# Singleton instance
manager = ConnectionManager()
