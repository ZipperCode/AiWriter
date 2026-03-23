"""Tests for UsageService."""

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage_record import UsageRecord
from app.services.usage_service import UsageService

import socket as _socket
import pytest

def _pg_ok():
    try:
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        s.settimeout(1)
        r = s.connect_ex(("127.0.0.1", 5432)) == 0
        s.close()
        return r
    except Exception:
        return False

pytestmark = pytest.mark.skipif(not _pg_ok(), reason="PostgreSQL not available")


async def test_record_usage(db_session: AsyncSession):
    """Test recording a usage record."""
    svc = UsageService(db_session)

    record = await svc.record_usage(
        model="gpt-4",
        input_tokens=100,
        output_tokens=50,
        cost=0.15,
        agent_name="writer",
    )

    assert isinstance(record, UsageRecord)
    assert record.model == "gpt-4"
    assert record.input_tokens == 100
    assert record.output_tokens == 50
    assert record.cost == 0.15
    assert record.agent_name == "writer"


async def test_record_usage_with_job_run_id(db_session: AsyncSession):
    """Test recording usage with job_run_id (without provider_config_id to avoid FK constraint)."""
    from app.models.job_run import JobRun
    from app.models.project import Project

    # Create a project first
    project = Project(title="Test", genre="xuanhuan", status="active", settings={})
    db_session.add(project)
    await db_session.flush()

    # Create a job run
    job_run = JobRun(
        project_id=project.id,
        job_type="pipeline_write",
        status="pending",
        agent_chain=[],
        result={},
    )
    db_session.add(job_run)
    await db_session.flush()

    svc = UsageService(db_session)

    record = await svc.record_usage(
        model="gpt-3.5-turbo",
        input_tokens=50,
        output_tokens=30,
        cost=0.05,
        agent_name="auditor",
        job_run_id=job_run.id,
    )

    assert record.job_run_id == job_run.id


async def test_get_usage_summary(db_session: AsyncSession):
    """Test getting usage summary with totals."""
    svc = UsageService(db_session)

    # Record multiple usages
    await svc.record_usage(
        model="gpt-4",
        input_tokens=100,
        output_tokens=50,
        cost=0.15,
        agent_name="writer",
    )

    await svc.record_usage(
        model="gpt-3.5-turbo",
        input_tokens=200,
        output_tokens=100,
        cost=0.10,
        agent_name="auditor",
    )

    await svc.record_usage(
        model="gpt-4",
        input_tokens=50,
        output_tokens=25,
        cost=0.08,
        agent_name="reviser",
    )

    summary = await svc.get_summary()

    assert summary["total_input_tokens"] == 350  # 100 + 200 + 50
    assert summary["total_output_tokens"] == 175  # 50 + 100 + 25
    assert abs(summary["total_cost"] - 0.33) < 0.001  # 0.15 + 0.10 + 0.08
    assert summary["total_calls"] == 3


async def test_get_usage_by_model(db_session: AsyncSession):
    """Test getting usage grouped by model."""
    svc = UsageService(db_session)

    # Record usages for different models
    await svc.record_usage(
        model="gpt-4",
        input_tokens=100,
        output_tokens=50,
        cost=0.15,
    )

    await svc.record_usage(
        model="gpt-4",
        input_tokens=50,
        output_tokens=25,
        cost=0.08,
    )

    await svc.record_usage(
        model="gpt-3.5-turbo",
        input_tokens=200,
        output_tokens=100,
        cost=0.10,
    )

    by_model = await svc.get_by_model()

    # Should have 2 entries (one per model)
    assert len(by_model) == 2

    # Find gpt-4 entry
    gpt4_entry = next(m for m in by_model if m["model"] == "gpt-4")
    assert gpt4_entry["total_input_tokens"] == 150  # 100 + 50
    assert gpt4_entry["total_output_tokens"] == 75  # 50 + 25
    assert abs(gpt4_entry["total_cost"] - 0.23) < 0.001  # 0.15 + 0.08
    assert gpt4_entry["call_count"] == 2

    # Find gpt-3.5-turbo entry
    turbo_entry = next(m for m in by_model if m["model"] == "gpt-3.5-turbo")
    assert turbo_entry["total_input_tokens"] == 200
    assert turbo_entry["total_output_tokens"] == 100
    assert abs(turbo_entry["total_cost"] - 0.10) < 0.001
    assert turbo_entry["call_count"] == 1


async def test_get_usage_by_agent(db_session: AsyncSession):
    """Test getting usage grouped by agent_name."""
    svc = UsageService(db_session)

    # Record usages for different agents
    await svc.record_usage(
        model="gpt-4",
        input_tokens=100,
        output_tokens=50,
        cost=0.15,
        agent_name="writer",
    )

    await svc.record_usage(
        model="gpt-4",
        input_tokens=50,
        output_tokens=25,
        cost=0.08,
        agent_name="writer",
    )

    await svc.record_usage(
        model="gpt-3.5-turbo",
        input_tokens=200,
        output_tokens=100,
        cost=0.10,
        agent_name="auditor",
    )

    # Record without agent_name (should not be included)
    await svc.record_usage(
        model="gpt-4",
        input_tokens=30,
        output_tokens=20,
        cost=0.05,
    )

    by_agent = await svc.get_by_agent()

    # Should have 2 entries (writer and auditor, not the None one)
    assert len(by_agent) == 2

    # Find writer entry
    writer_entry = next(a for a in by_agent if a["agent_name"] == "writer")
    assert writer_entry["total_input_tokens"] == 150  # 100 + 50
    assert writer_entry["total_output_tokens"] == 75  # 50 + 25
    assert abs(writer_entry["total_cost"] - 0.23) < 0.001  # 0.15 + 0.08
    assert writer_entry["call_count"] == 2

    # Find auditor entry
    auditor_entry = next(a for a in by_agent if a["agent_name"] == "auditor")
    assert auditor_entry["total_input_tokens"] == 200
    assert auditor_entry["total_output_tokens"] == 100
    assert abs(auditor_entry["total_cost"] - 0.10) < 0.001
    assert auditor_entry["call_count"] == 1


async def test_get_summary_empty(db_session: AsyncSession):
    """Test getting summary when no records exist."""
    svc = UsageService(db_session)
    summary = await svc.get_summary()

    assert summary["total_input_tokens"] == 0
    assert summary["total_output_tokens"] == 0
    assert summary["total_cost"] == 0.0
    assert summary["total_calls"] == 0


async def test_get_by_model_empty(db_session: AsyncSession):
    """Test getting by model when no records exist."""
    svc = UsageService(db_session)
    by_model = await svc.get_by_model()

    assert len(by_model) == 0
    assert by_model == []


async def test_get_by_agent_empty(db_session: AsyncSession):
    """Test getting by agent when no records exist."""
    svc = UsageService(db_session)
    by_agent = await svc.get_by_agent()

    assert len(by_agent) == 0
    assert by_agent == []
