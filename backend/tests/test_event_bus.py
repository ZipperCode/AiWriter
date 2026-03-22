import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from app.events.event_bus import EventBus, PipelineEvent


def test_pipeline_event_creation():
    event = PipelineEvent(
        job_run_id=uuid4(),
        event_type="agent_start",
        agent_name="writer",
        data={"phase": 1},
    )
    assert event.event_type == "agent_start"
    assert event.agent_name == "writer"


def test_pipeline_event_to_json():
    event = PipelineEvent(
        job_run_id=uuid4(),
        event_type="agent_complete",
        agent_name="auditor",
        data={"score": 85},
    )
    j = event.to_json()
    assert '"agent_complete"' in j
    assert '"auditor"' in j


def test_pipeline_event_from_json_roundtrip():
    original = PipelineEvent(
        job_run_id=uuid4(),
        event_type="agent_error",
        agent_name="auditor",
        data={"error": "timeout"},
    )
    restored = PipelineEvent.from_json(original.to_json())
    assert str(restored.job_run_id) == str(original.job_run_id)
    assert restored.event_type == original.event_type
    assert restored.agent_name == original.agent_name
    assert restored.data == original.data


async def test_event_bus_publish():
    mock_redis = AsyncMock()
    bus = EventBus(mock_redis)
    event = PipelineEvent(
        job_run_id=uuid4(),
        event_type="agent_start",
        agent_name="writer",
    )
    await bus.publish(event)
    mock_redis.publish.assert_called_once()
    channel = mock_redis.publish.call_args[0][0]
    assert "pipeline:" in channel


def test_event_bus_channel_name():
    job_id = uuid4()
    assert EventBus.channel_name(job_id) == f"pipeline:{job_id}"
