import pytest
from uuid import uuid4
from app.events.event_bus import PipelineEvent


async def test_pipeline_event_serialization():
    event = PipelineEvent(
        job_run_id=uuid4(),
        event_type="agent_start",
        agent_name="writer",
        data={"phase": 1},
    )
    j = event.to_json()
    restored = PipelineEvent.from_json(j)
    assert restored.event_type == event.event_type
    assert restored.agent_name == event.agent_name
    assert restored.data == event.data


def test_ws_route_registered():
    """WebSocket route should be registered."""
    from app.main import app
    ws_routes = [r.path for r in app.routes if hasattr(r, 'path')]
    assert any("/ws/" in r for r in ws_routes)


async def test_pipeline_event_all_types():
    """Test all event types serialize correctly."""
    for event_type in ["agent_start", "agent_progress", "agent_complete", "agent_error", "pipeline_complete", "pipeline_error"]:
        event = PipelineEvent(job_run_id=uuid4(), event_type=event_type, agent_name="test")
        restored = PipelineEvent.from_json(event.to_json())
        assert restored.event_type == event_type


def test_pipeline_event_empty_data():
    event = PipelineEvent(job_run_id=uuid4(), event_type="agent_start")
    assert event.data == {}
    assert event.agent_name == ""
    restored = PipelineEvent.from_json(event.to_json())
    assert restored.data == {}
