import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.export_service import ExportService


@pytest.fixture
def tmp_storage_dir(tmp_path):
    """Create a temporary storage directory for exports."""
    return str(tmp_path / "storage")


def _mock_project():
    """Create a mock project."""
    p = MagicMock()
    p.title = "Test Novel"
    p.id = uuid4()
    return p


def _mock_chapters():
    """Create a list of mock chapters with drafts."""
    ch1 = MagicMock()
    ch1.title = "Chapter 1"
    ch1.sort_order = 1
    draft1 = MagicMock()
    draft1.content = "Content of chapter 1."
    draft1.status = "final"
    ch1.drafts = [draft1]

    ch2 = MagicMock()
    ch2.title = "Chapter 2"
    ch2.sort_order = 2
    draft2 = MagicMock()
    draft2.content = "Content of chapter 2."
    draft2.status = "draft"
    ch2.drafts = [draft2]

    return [ch1, ch2]


@pytest.mark.asyncio
async def test_export_service_init_creates_directory(tmp_storage_dir):
    """Test that ExportService creates the storage directory if it doesn't exist."""
    db = AsyncMock()
    service = ExportService(db, storage_dir=tmp_storage_dir)

    export_dir = os.path.join(tmp_storage_dir, "exports")
    assert os.path.exists(export_dir)
    assert os.path.isdir(export_dir)


@pytest.mark.asyncio
async def test_export_txt(tmp_storage_dir):
    """Test exporting project content as plain text."""
    db = AsyncMock()
    service = ExportService(db, storage_dir=tmp_storage_dir)

    project = _mock_project()
    chapters = _mock_chapters()

    # Mock the service methods
    service._get_project = AsyncMock(return_value=project)
    service._get_chapters = AsyncMock(return_value=chapters)

    project_id = uuid4()
    filepath = await service.export_txt(project_id)

    assert filepath is not None
    assert os.path.exists(filepath)
    assert filepath.endswith(".txt")

    # Read and verify content
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    assert "Test Novel" in content
    assert "Chapter 1" in content
    assert "Content of chapter 1." in content
    assert "Chapter 2" in content
    assert "Content of chapter 2." in content


@pytest.mark.asyncio
async def test_export_markdown(tmp_storage_dir):
    """Test exporting project content as markdown."""
    db = AsyncMock()
    service = ExportService(db, storage_dir=tmp_storage_dir)

    project = _mock_project()
    chapters = _mock_chapters()

    # Mock the service methods
    service._get_project = AsyncMock(return_value=project)
    service._get_chapters = AsyncMock(return_value=chapters)

    project_id = uuid4()
    filepath = await service.export_markdown(project_id)

    assert filepath is not None
    assert os.path.exists(filepath)
    assert filepath.endswith(".md")

    # Read and verify content
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Check for markdown headers
    assert "# Test Novel" in content
    assert "## Chapter 1" in content
    assert "## Chapter 2" in content
    assert "Content of chapter 1." in content
    assert "Content of chapter 2." in content


@pytest.mark.asyncio
async def test_export_epub(tmp_storage_dir):
    """Test exporting project content as EPUB."""
    db = AsyncMock()
    service = ExportService(db, storage_dir=tmp_storage_dir)

    project = _mock_project()
    chapters = _mock_chapters()

    # Mock the service methods
    service._get_project = AsyncMock(return_value=project)
    service._get_chapters = AsyncMock(return_value=chapters)

    project_id = uuid4()
    filepath = await service.export_epub(project_id)

    assert filepath is not None
    assert os.path.exists(filepath)
    assert filepath.endswith(".epub")


@pytest.mark.asyncio
async def test_export_service_get_final_content(tmp_storage_dir):
    """Test the _get_final_content method returns the final draft content."""
    db = AsyncMock()
    service = ExportService(db, storage_dir=tmp_storage_dir)

    # Create a mock chapter with multiple drafts
    chapter = MagicMock()
    final_draft = MagicMock()
    final_draft.content = "This is the final content."
    final_draft.status = "final"

    draft_draft = MagicMock()
    draft_draft.content = "This is a draft."
    draft_draft.status = "draft"

    chapter.drafts = [draft_draft, final_draft]

    content = service._get_final_content(chapter)
    assert content == "This is the final content."


@pytest.mark.asyncio
async def test_export_service_get_final_content_no_final_draft(tmp_storage_dir):
    """Test _get_final_content returns latest draft if no 'final' status exists."""
    db = AsyncMock()
    service = ExportService(db, storage_dir=tmp_storage_dir)

    chapter = MagicMock()
    draft1 = MagicMock()
    draft1.content = "First draft."
    draft1.status = "draft"

    draft2 = MagicMock()
    draft2.content = "Latest draft."
    draft2.status = "draft"

    chapter.drafts = [draft1, draft2]

    content = service._get_final_content(chapter)
    assert content == "Latest draft."


@pytest.mark.asyncio
async def test_export_service_get_final_content_no_drafts(tmp_storage_dir):
    """Test _get_final_content returns empty string if no drafts exist."""
    db = AsyncMock()
    service = ExportService(db, storage_dir=tmp_storage_dir)

    chapter = MagicMock()
    chapter.drafts = []

    content = service._get_final_content(chapter)
    assert content == ""
