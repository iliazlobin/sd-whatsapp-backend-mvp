import uuid
from typing import Any


class ConnectionManager:
    """In-memory WebSocket connection map.

    Single-server singleton: dict[user_id, set[WebSocket-like]].
    Concurrency-safe via asyncio (single-threaded event loop).
    """

    def __init__(self) -> None:
        self._connections: dict[uuid.UUID, set[Any]] = {}

    async def connect(self, user_id: uuid.UUID, websocket: Any) -> None:
        await websocket.accept()
        if user_id not in self._connections:
            self._connections[user_id] = set()
        self._connections[user_id].add(websocket)

    def disconnect(self, user_id: uuid.UUID, websocket: Any) -> None:
        if user_id in self._connections:
            self._connections[user_id].discard(websocket)
            if not self._connections[user_id]:
                del self._connections[user_id]

    async def send_to_user(self, user_id: uuid.UUID, message: str) -> None:
        connections = self._connections.get(user_id, set())
        dead: list[Any] = []
        for ws in connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(user_id, ws)

    def is_online(self, user_id: uuid.UUID) -> bool:
        return user_id in self._connections and len(self._connections[user_id]) > 0


# Module-level singleton
connection_manager = ConnectionManager()
