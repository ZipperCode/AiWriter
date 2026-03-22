"""Redis Pub/Sub event bus for pipeline progress."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import AsyncIterator
from uuid import UUID

from redis.asyncio import Redis


@dataclass
class PipelineEvent:
    """Event published during pipeline execution."""
    job_run_id: UUID
    event_type: str
    agent_name: str = ""
    data: dict = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_json(self) -> str:
        return json.dumps({
            "job_run_id": str(self.job_run_id),
            "event_type": self.event_type,
            "agent_name": self.agent_name,
            "data": self.data,
            "timestamp": self.timestamp,
        }, ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> PipelineEvent:
        d = json.loads(raw)
        return cls(
            job_run_id=UUID(d["job_run_id"]),
            event_type=d["event_type"],
            agent_name=d.get("agent_name", ""),
            data=d.get("data", {}),
            timestamp=d.get("timestamp", ""),
        )

    @staticmethod
    def channel_name(job_run_id: UUID) -> str:
        return f"pipeline:{job_run_id}"


class EventBus:
    """Redis Pub/Sub event bus."""

    def __init__(self, redis: Redis):
        self.redis = redis

    @staticmethod
    def channel_name(job_run_id: UUID) -> str:
        return PipelineEvent.channel_name(job_run_id)

    async def publish(self, event: PipelineEvent) -> None:
        channel = self.channel_name(event.job_run_id)
        await self.redis.publish(channel, event.to_json())

    async def subscribe(self, job_run_id: UUID) -> AsyncIterator[PipelineEvent]:
        channel = self.channel_name(job_run_id)
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            while True:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg["type"] == "message":
                    raw = msg["data"]
                    if isinstance(raw, bytes):
                        raw = raw.decode()
                    yield PipelineEvent.from_json(raw)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
