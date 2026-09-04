import asyncio
import json
from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    """Tracks WebSocket subscribers per survey_id and broadcasts JSON events.

    Frontend does not receive full payloads over the socket, only lightweight
    events (spec section 41) and then fetches the authoritative data via the
    REST API - keeps the realtime channel simple and consistent with the DB.
    """

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, survey_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[survey_id].add(websocket)

    async def disconnect(self, survey_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections[survey_id].discard(websocket)
            if not self._connections[survey_id]:
                self._connections.pop(survey_id, None)

    async def broadcast(self, survey_id: str, event: str, payload: dict) -> None:
        message = json.dumps({"event": event, "survey_id": survey_id, **payload})
        dead: list[WebSocket] = []
        for ws in list(self._connections.get(survey_id, set())):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(survey_id, ws)

    def connection_count(self) -> int:
        return sum(len(conns) for conns in self._connections.values())


manager = ConnectionManager()
