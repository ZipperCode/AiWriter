import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, verify_token
from app.main import app
from app.models.audit_record import AuditRecord
from app.models.chapter import Chapter
from app.models.draft import Draft
from app.models.project import Project
from app.models.volume import Volume


async def test_list_dimensions(db_session: AsyncSession):
    """GET /api/audit/dimensions should return all 33 dimensions."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[verify_token] = lambda: "test-token"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/audit/dimensions",
            headers={"Authorization": "Bearer test-token"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 33


async def test_list_audit_records(db_session: AsyncSession):
    """GET /api/chapters/{id}/audit-records should return audit records."""
    project = Project(title="T", genre="xuanhuan", status="active", settings={})
    db_session.add(project)
    await db_session.flush()

    volume = Volume(project_id=project.id, title="V1", objective="t", sort_order=1)
    db_session.add(volume)
    await db_session.flush()

    ch = Chapter(project_id=project.id, volume_id=volume.id, title="C1", sort_order=1, status="final")
    db_session.add(ch)
    await db_session.flush()

    draft = Draft(chapter_id=ch.id, version=1, content="text", word_count=100)
    db_session.add(draft)
    await db_session.flush()

    record = AuditRecord(
        chapter_id=ch.id, draft_id=draft.id,
        dimension="ai_trace_detection", category="style",
        score=8.5, severity="pass", message="Clean text",
        evidence=[],
    )
    db_session.add(record)
    await db_session.flush()

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[verify_token] = lambda: "test-token"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/chapters/{ch.id}/audit-records",
            headers={"Authorization": "Bearer test-token"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["dimension"] == "ai_trace_detection"


async def test_run_quick_audit(db_session: AsyncSession):
    """POST /api/audit/quick should run deterministic checks only."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[verify_token] = lambda: "test-token"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/audit/quick",
            headers={"Authorization": "Bearer test-token"},
            json={"text": "他不禁缓缓叹了口气。" * 20},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "pass_rate" in data
    assert "scores" in data
