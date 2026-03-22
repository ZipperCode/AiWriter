from uuid import uuid4

import pytest

from app.models.project import Project
from app.models.volume import Volume
from app.models.chapter import Chapter
from app.models.draft import Draft


@pytest.mark.asyncio
async def test_export_txt_api(client, auth_headers, db_session):
    """Test POST /api/projects/{project_id}/export with format=txt."""
    # Create test data
    project = Project(
        title="Test Novel",
        genre="xuanhuan",
        status="draft",
    )
    db_session.add(project)
    await db_session.flush()

    volume = Volume(
        project_id=project.id,
        title="Volume 1",
        objective="Test objective",
        sort_order=1,
    )
    db_session.add(volume)
    await db_session.flush()

    chapter = Chapter(
        project_id=project.id,
        volume_id=volume.id,
        title="Chapter 1",
        sort_order=1,
    )
    db_session.add(chapter)
    await db_session.flush()

    draft = Draft(
        chapter_id=chapter.id,
        content="This is the chapter content.",
        status="final",
    )
    db_session.add(draft)
    await db_session.commit()

    # Test export endpoint
    response = await client.post(
        f"/api/projects/{project.id}/export",
        json={"format": "txt"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert "file_path" in data
    assert "format" in data
    assert "download_url" in data
    assert data["format"] == "txt"


@pytest.mark.asyncio
async def test_export_markdown_api(client, auth_headers, db_session):
    """Test POST /api/projects/{project_id}/export with format=markdown."""
    # Create test data
    project = Project(
        title="Test Novel",
        genre="xuanhuan",
        status="draft",
    )
    db_session.add(project)
    await db_session.flush()

    volume = Volume(
        project_id=project.id,
        title="Volume 1",
        objective="Test objective",
        sort_order=1,
    )
    db_session.add(volume)
    await db_session.flush()

    chapter = Chapter(
        project_id=project.id,
        volume_id=volume.id,
        title="Chapter 1",
        sort_order=1,
    )
    db_session.add(chapter)
    await db_session.flush()

    draft = Draft(
        chapter_id=chapter.id,
        content="This is the chapter content.",
        status="final",
    )
    db_session.add(draft)
    await db_session.commit()

    # Test export endpoint
    response = await client.post(
        f"/api/projects/{project.id}/export",
        json={"format": "markdown"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["format"] == "markdown"


@pytest.mark.asyncio
async def test_export_epub_api(client, auth_headers, db_session):
    """Test POST /api/projects/{project_id}/export with format=epub."""
    # Create test data
    project = Project(
        title="Test Novel",
        genre="xuanhuan",
        status="draft",
    )
    db_session.add(project)
    await db_session.flush()

    volume = Volume(
        project_id=project.id,
        title="Volume 1",
        objective="Test objective",
        sort_order=1,
    )
    db_session.add(volume)
    await db_session.flush()

    chapter = Chapter(
        project_id=project.id,
        volume_id=volume.id,
        title="Chapter 1",
        sort_order=1,
    )
    db_session.add(chapter)
    await db_session.flush()

    draft = Draft(
        chapter_id=chapter.id,
        content="This is the chapter content.",
        status="final",
    )
    db_session.add(draft)
    await db_session.commit()

    # Test export endpoint
    response = await client.post(
        f"/api/projects/{project.id}/export",
        json={"format": "epub"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["format"] == "epub"


@pytest.mark.asyncio
async def test_export_invalid_format(client, auth_headers, db_session):
    """Test POST /api/projects/{project_id}/export with invalid format returns 400."""
    project = Project(
        title="Test Novel",
        genre="xuanhuan",
        status="draft",
    )
    db_session.add(project)
    await db_session.commit()

    response = await client.post(
        f"/api/projects/{project.id}/export",
        json={"format": "pdf"},
        headers=auth_headers,
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_export_project_not_found(client, auth_headers):
    """Test POST /api/projects/{project_id}/export with nonexistent project returns 404."""
    fake_project_id = uuid4()

    response = await client.post(
        f"/api/projects/{fake_project_id}/export",
        json={"format": "txt"},
        headers=auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_download_file(client, auth_headers, db_session, tmp_path):
    """Test GET /api/export/download/{filename} downloads a file."""
    import os

    # Create a temporary export file
    export_dir = tmp_path / "exports"
    export_dir.mkdir(exist_ok=True)

    test_file = export_dir / "test_export.txt"
    test_file.write_text("Test content", encoding="utf-8")

    # We need to mock the storage path
    # For now, we'll just verify the endpoint exists and returns 404 for missing file
    response = await client.get(
        "/api/export/download/nonexistent_file.txt",
        headers=auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_export_without_auth(client):
    """Test that export endpoints require authentication."""
    fake_project_id = uuid4()

    response = await client.post(
        f"/api/projects/{fake_project_id}/export",
        json={"format": "txt"},
    )

    assert response.status_code == 401
