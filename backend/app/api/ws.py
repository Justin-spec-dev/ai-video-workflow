"""WebSocket /ws/events (SPEC §7)."""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..core.events import bus

router = APIRouter()
logger = logging.getLogger("ws")


@router.websocket("/ws/events")
async def ws_events(websocket: WebSocket):
    await websocket.accept()
    queue = bus.subscribe()
    try:
        while True:
            msg = await queue.get()
            await websocket.send_text(json.dumps(msg, ensure_ascii=False, default=str))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug("ws 连接结束: %s", e)
    finally:
        bus.unsubscribe(queue)
