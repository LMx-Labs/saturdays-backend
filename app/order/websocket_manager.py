import uuid
from typing import Any

from fastapi import WebSocket


class OrderWebSocketManager:
    """In-process WebSocket Manager for branch kitchen terminals (ADR-0010)."""

    def __init__(self) -> None:
        # Maps branch_id -> list of active WebSockets
        self.active_connections: dict[uuid.UUID, list[WebSocket]] = {}

    async def connect(self, branch_id: uuid.UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        if branch_id not in self.active_connections:
            self.active_connections[branch_id] = []
        self.active_connections[branch_id].append(websocket)

    def disconnect(self, branch_id: uuid.UUID, websocket: WebSocket) -> None:
        if branch_id in self.active_connections:
            if websocket in self.active_connections[branch_id]:
                self.active_connections[branch_id].remove(websocket)
            if not self.active_connections[branch_id]:
                del self.active_connections[branch_id]

    async def broadcast_to_branch(
        self, branch_id: uuid.UUID, message: dict[str, Any]
    ) -> None:
        if branch_id in self.active_connections:
            for connection in list(self.active_connections[branch_id]):
                try:
                    await connection.send_json(message)
                except Exception:  # noqa: BLE001
                    self.disconnect(branch_id, connection)


ws_manager = OrderWebSocketManager()
