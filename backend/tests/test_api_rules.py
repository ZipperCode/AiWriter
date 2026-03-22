"""Tests for Book Rules CRUD API endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, verify_token
from app.main import app
from app.models.book_rules import BookRules
from app.models.project import Project


async def _setup_client(db_session: AsyncSession):
    """Create an AsyncClient that shares the given db_session."""

    async def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    app.dependency_overrides[verify_token] = lambda: "test-token"
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


AUTH = {"Authorization": "Bearer test-token"}


async def _create_project_with_rules(
    db_session: AsyncSession,
    genre: str = "xuanhuan",
    base_guardrails: dict | None = None,
    genre_profile: dict | None = None,
    custom_rules: dict | None = None,
):
    """Helper: insert a project + book_rules row, return (project, rules)."""
    project = Project(title="Test Novel", genre=genre, status="active", settings={})
    db_session.add(project)
    await db_session.flush()

    rules = BookRules(
        project_id=project.id,
        base_guardrails=base_guardrails or {},
        genre_profile=genre_profile or {},
        custom_rules=custom_rules or {},
    )
    db_session.add(rules)
    await db_session.flush()
    return project, rules


# --- GET /api/rules/genres ---


async def test_list_genre_profiles(db_session: AsyncSession):
    """GET /api/rules/genres should return all available genre profiles."""
    async with await _setup_client(db_session) as client:
        resp = await client.get("/api/rules/genres", headers=AUTH)

    assert resp.status_code == 200
    data = resp.json()
    assert "genres" in data
    names = [g["name"] for g in data["genres"]]
    assert "xuanhuan" in names
    assert "xianxia" in names
    assert "urban" in names
    assert len(data["genres"]) == 3


async def test_list_genre_profiles_structure(db_session: AsyncSession):
    """Each genre profile should have required fields."""
    async with await _setup_client(db_session) as client:
        resp = await client.get("/api/rules/genres", headers=AUTH)

    data = resp.json()
    for genre in data["genres"]:
        assert "name" in genre
        assert "zh_name" in genre
        assert "disabled_dimensions" in genre
        assert "taboos" in genre
        assert "settings" in genre
        assert isinstance(genre["disabled_dimensions"], list)
        assert isinstance(genre["taboos"], list)


# --- GET /api/projects/{project_id}/rules ---


async def test_get_book_rules(db_session: AsyncSession):
    """GET /api/projects/{id}/rules should return book rules."""
    project, rules = await _create_project_with_rules(
        db_session,
        base_guardrails={"rules": [{"id": "bg_01"}]},
        genre_profile={"name": "xuanhuan"},
        custom_rules={"rules": []},
    )

    async with await _setup_client(db_session) as client:
        resp = await client.get(
            f"/api/projects/{project.id}/rules", headers=AUTH
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == str(project.id)
    assert data["base_guardrails"] == {"rules": [{"id": "bg_01"}]}
    assert data["genre_profile"]["name"] == "xuanhuan"


async def test_get_book_rules_not_found(db_session: AsyncSession):
    """GET /api/projects/{id}/rules should 404 when no rules exist."""
    project = Project(title="No Rules", genre="xuanhuan", status="active", settings={})
    db_session.add(project)
    await db_session.flush()

    async with await _setup_client(db_session) as client:
        resp = await client.get(
            f"/api/projects/{project.id}/rules", headers=AUTH
        )

    assert resp.status_code == 404


# --- PUT /api/projects/{project_id}/rules ---


async def test_update_book_rules(db_session: AsyncSession):
    """PUT /api/projects/{id}/rules should update book rules."""
    project, rules = await _create_project_with_rules(db_session)

    async with await _setup_client(db_session) as client:
        resp = await client.put(
            f"/api/projects/{project.id}/rules",
            headers=AUTH,
            json={
                "genre_profile": {"name": "xianxia"},
                "custom_rules": {
                    "custom_rules": [{"id": "c1", "rule": "No filler"}]
                },
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["genre_profile"]["name"] == "xianxia"
    assert data["custom_rules"]["custom_rules"][0]["id"] == "c1"


async def test_update_book_rules_partial(db_session: AsyncSession):
    """PUT should allow partial update (only fields provided)."""
    project, rules = await _create_project_with_rules(
        db_session,
        base_guardrails={"existing": True},
        genre_profile={"name": "xuanhuan"},
    )

    async with await _setup_client(db_session) as client:
        resp = await client.put(
            f"/api/projects/{project.id}/rules",
            headers=AUTH,
            json={"genre_profile": {"name": "urban"}},
        )

    assert resp.status_code == 200
    data = resp.json()
    # genre_profile updated
    assert data["genre_profile"]["name"] == "urban"
    # base_guardrails unchanged
    assert data["base_guardrails"]["existing"] is True


async def test_update_book_rules_not_found(db_session: AsyncSession):
    """PUT /api/projects/{id}/rules should 404 when no rules exist."""
    project = Project(title="No Rules", genre="xuanhuan", status="active", settings={})
    db_session.add(project)
    await db_session.flush()

    async with await _setup_client(db_session) as client:
        resp = await client.put(
            f"/api/projects/{project.id}/rules",
            headers=AUTH,
            json={"genre_profile": {"name": "urban"}},
        )

    assert resp.status_code == 404


# --- GET /api/projects/{project_id}/rules/merged ---


async def test_get_merged_rules(db_session: AsyncSession):
    """GET /api/projects/{id}/rules/merged should return merged three-layer rules."""
    project, rules = await _create_project_with_rules(
        db_session,
        genre_profile={"name": "xuanhuan"},
        custom_rules={"custom_rules": [{"id": "c1", "rule": "test"}]},
    )

    async with await _setup_client(db_session) as client:
        resp = await client.get(
            f"/api/projects/{project.id}/rules/merged", headers=AUTH
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "guardrails" in data
    assert "taboos" in data
    assert "custom_rules" in data
    assert "settings" in data
    assert "disabled_dimensions" in data
    assert "prompt_text" in data
    # Base guardrails present
    assert len(data["guardrails"]) >= 20
    # Genre taboos present (xuanhuan has 4)
    assert len(data["taboos"]) >= 3
    # Custom rule present
    assert any(r["id"] == "c1" for r in data["custom_rules"])
    # Prompt text is non-empty
    assert len(data["prompt_text"]) > 100


async def test_get_merged_rules_no_genre(db_session: AsyncSession):
    """Merged rules without genre should still have guardrails."""
    project, rules = await _create_project_with_rules(
        db_session,
        genre_profile={},
        custom_rules={},
    )

    async with await _setup_client(db_session) as client:
        resp = await client.get(
            f"/api/projects/{project.id}/rules/merged", headers=AUTH
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["guardrails"]) >= 20
    assert data["taboos"] == []
    assert data["custom_rules"] == []


async def test_get_merged_rules_not_found(db_session: AsyncSession):
    """GET /api/projects/{id}/rules/merged should 404 when no rules exist."""
    project = Project(title="No Rules", genre="xuanhuan", status="active", settings={})
    db_session.add(project)
    await db_session.flush()

    async with await _setup_client(db_session) as client:
        resp = await client.get(
            f"/api/projects/{project.id}/rules/merged", headers=AUTH
        )

    assert resp.status_code == 404


# --- Auth tests ---


async def test_rules_endpoints_require_auth(db_session: AsyncSession):
    """All rules endpoints should require authentication."""
    app.dependency_overrides.clear()
    async def _override():
        yield db_session
    app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/rules/genres")
        assert resp.status_code in (401, 403)

        resp = await client.get("/api/projects/00000000-0000-0000-0000-000000000000/rules")
        assert resp.status_code in (401, 403)
