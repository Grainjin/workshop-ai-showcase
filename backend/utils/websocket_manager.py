"""WebSocket connection manager.

Users may have multiple connections; stored as `dict[user_id, list[WebSocket]]`.
Chat history is in the database; this manager handles live push only.
"""

from fastapi import WebSocket


class WebSocketManager:
    def __init__(self):
        self.active_connections: dict[int, list[WebSocket]] = {}

    async def connect(
        self,
        user_id: int,
        websocket: WebSocket,
        *,
        already_accepted: bool = False,
    ):
        if not already_accepted:
            await websocket.accept()

        if user_id not in self.active_connections:
            self.active_connections[user_id] = []

        self.active_connections[user_id].append(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket):
        user_connections = self.active_connections.get(user_id)

        if not user_connections:
            return

        if websocket in user_connections:
            user_connections.remove(websocket)

        if not user_connections:
            del self.active_connections[user_id]

    async def send_to_user(self, user_id: int, data: dict):
        user_connections = self.active_connections.get(user_id, [])
        disconnected_connections = []

        for websocket in list(user_connections):
            try:
                await websocket.send_json(data)
            except RuntimeError:
                disconnected_connections.append(websocket)

        for websocket in disconnected_connections:
            if websocket in user_connections:
                user_connections.remove(websocket)

        if not user_connections and user_id in self.active_connections:
            del self.active_connections[user_id]

    async def broadcast(self, data: dict):
        for user_id in list(self.active_connections.keys()):
            await self.send_to_user(user_id, data)

    def is_online(self, user_id: int):
        return user_id in self.active_connections


websocket_manager = WebSocketManager()
