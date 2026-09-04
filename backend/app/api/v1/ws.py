from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import decode_access_token
from app.realtime.manager import manager

router = APIRouter(tags=["realtime"])


@router.websocket("/ws/surveys/{survey_id}")
async def survey_events(websocket: WebSocket, survey_id: str) -> None:
    token = websocket.query_params.get("token")
    if not token or not decode_access_token(token):
        await websocket.close(code=4401)
        return

    await manager.connect(survey_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(survey_id, websocket)
