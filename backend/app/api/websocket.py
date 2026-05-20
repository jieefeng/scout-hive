import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.engine.event_bus import EventBus

router = APIRouter(tags=["websocket"])

event_bus: EventBus = None
connected_clients: set[WebSocket] = set()


def init_router(bus: EventBus):
    global event_bus
    event_bus = bus

    async def broadcast_event(event):
        disconnected = set()
        for ws in connected_clients:
            try:
                await ws.send_json(event.model_dump())
            except Exception:
                disconnected.add(ws)
        connected_clients.difference_update(disconnected)

    event_bus.subscribe("node_started", broadcast_event)
    event_bus.subscribe("node_completed", broadcast_event)
    event_bus.subscribe("node_failed", broadcast_event)
    event_bus.subscribe("task_completed", broadcast_event)
    event_bus.subscribe("review_feedback", broadcast_event)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_clients.discard(websocket)
