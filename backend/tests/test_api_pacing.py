# backend/tests/test_api_pacing.py
import pytest
from uuid import uuid4
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from app.main import app
from app.models.project import Project
from app.models.volume import Volume
from app.models.chapter import Chapter
from app.models.pacing_meta import PacingMeta
from app.api.deps import get_db, verify_token


async def _setup_project_with_pacing(db: AsyncSession):
    project = Project(title="T", genre="xuanhuan", status="active", settings={})
    db.add(project)
    await db.flush()

    volume = Volume(project_id=project.id, title="V1", objective="t", sort_order=1)
    db.add(volume)
    await db.flush()

    for i in range(1, 4):
        ch = Chapter(
            project_id=project.id, volume_id=volume.id,
            title=f"Ch{i}", sort_order=i, status="final",
        )
        db.add(ch)
        await db.flush()
        pm = PacingMeta(
            chapter_id=ch.id,
            quest_ratio=0.6, fire_ratio=0.2, constellation_ratio=0.2,
            highlight_count=1, highlight_types=["越级反杀"],
            tension_level=0.5, strand_tags=["quest", "fire"],
        )
        db.add(pm)

    await db.flush()
    return project


async def test_get_pacing_analysis(db_session: AsyncSession):
    """GET /api/projects/{id}/pacing should return pacing analysis."""
    project = await _setup_project_with_pacing(db_session)

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[verify_token] = lambda: "test-token"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/projects/{project.id}/pacing",
            headers={"Authorization": "Bearer test-token"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "chapter_pacing" in data
    assert data["avg_quest_ratio"] > 0


async def test_get_red_lines(db_session: AsyncSession):
    """GET /api/projects/{id}/pacing/red-lines should return violations."""
    project = await _setup_project_with_pacing(db_session)

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[verify_token] = lambda: "test-token"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/projects/{project.id}/pacing/red-lines",
            headers={"Authorization": "Bearer test-token"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


async def test_get_pacing_suggestion(db_session: AsyncSession):
    """GET /api/projects/{id}/pacing/suggestion should return suggestion."""
    project = await _setup_project_with_pacing(db_session)

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[verify_token] = lambda: "test-token"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/projects/{project.id}/pacing/suggestion",
            headers={"Authorization": "Bearer test-token"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "recommended_strands" in data
    assert "tension_suggestion" in data
