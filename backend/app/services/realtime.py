from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import List

from fastapi import WebSocket

from app.models import LeadAssignmentStatus


@dataclass
class AssignmentEventOut:
    lead_id: str
    caller_id: str | None
    assignment_status: LeadAssignmentStatus
    assignment_reason: str
    timestamp: datetime


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_assignment(self, event: AssignmentEventOut) -> None:
        if not self.active_connections:
            return

        data = asdict(event)
        # Pydantic / JSON can't handle enums and datetimes directly here,
        # so normalise them.
        data["assignment_status"] = event.assignment_status.value
        data["timestamp"] = event.timestamp.isoformat()

        disconnected: list[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_json({"type": "assignment", "payload": data})
            except Exception:
                disconnected.append(connection)
        for ws in disconnected:
            self.disconnect(ws)


connection_manager = ConnectionManager()

