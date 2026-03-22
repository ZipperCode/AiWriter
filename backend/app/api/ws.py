"""WebSocket endpoint for real-time pipeline progress."""

from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis

from app.config import settings
from app.events.event_bus import EventBus

router = APIRouter()


@router.websocket("/ws/{job_run_id}")
async def pipeline_ws(websocket: WebSocket, job_run_id: UUID):
    """Stream pipeline events via WebSocket."""
    await websocket.accept()

    redis = Redis.from_url(settings.redis_url)
    bus = EventBus(redis)

    try:
        async for event in bus.subscribe(job_run_id):
            await websocket.send_text(event.to_json())
            if event.event_type in ("pipeline_complete", "pipeline_error"):
                break
    except WebSocketDisconnect:
        pass
    finally:
        await redis.close()
