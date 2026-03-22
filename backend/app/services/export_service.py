import os
from datetime import datetime
from uuid import UUID

from ebooklib import epub
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.chapter import Chapter
from app.models.project import Project
from app.models.volume import Volume


class ExportService:
    """Service for exporting project content in various formats."""

    def __init__(self, db: AsyncSession, storage_dir: str = "./storage"):
        self.db = db
        self.export_dir = os.path.join(storage_dir, "exports")
        os.makedirs(self.export_dir, exist_ok=True)

    async def _get_project(self, project_id: UUID) -> Project:
        """Fetch project by ID."""
        result = await self.db.execute(
            select(Project).where(Project.id == project_id)
        )
        return result.scalar_one_or_none()

    async def _get_chapters(self, project_id: UUID) -> list[Chapter]:
        """
        Fetch all chapters for a project, ordered by volume and chapter sort_order.
        Eagerly loads drafts.
        """
        query = (
            select(Chapter)
            .where(Chapter.project_id == project_id)
            .options(selectinload(Chapter.drafts))
            .order_by(Chapter.sort_order)
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    def _get_final_content(self, chapter: Chapter) -> str:
        """
        Get the content from a chapter's final draft, or latest draft if no final exists.
        Returns empty string if no drafts exist.
        """
        if not chapter.drafts:
            return ""

        # Look for "final" status draft
        for draft in chapter.drafts:
            if draft.status == "final":
                return draft.content

        # Otherwise, return the last draft
        return chapter.drafts[-1].content

    async def export_txt(self, project_id: UUID) -> str:
        """Export project as plain text file. Returns filepath."""
        project = await self._get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        chapters = await self._get_chapters(project_id)

        # Build content
        lines = []
        lines.append(project.title)
        lines.append("=" * len(project.title))
        lines.append("")

        for chapter in chapters:
            lines.append(f"\n{chapter.title}")
            lines.append("-" * len(chapter.title))
            content = self._get_final_content(chapter)
            lines.append(content)
            lines.append("")

        # Write to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{project.title}_{timestamp}.txt"
        filepath = os.path.join(self.export_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return filepath

    async def export_markdown(self, project_id: UUID) -> str:
        """Export project as markdown file. Returns filepath."""
        project = await self._get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        chapters = await self._get_chapters(project_id)

        # Build content
        lines = []
        lines.append(f"# {project.title}")
        lines.append("")

        for chapter in chapters:
            lines.append(f"## {chapter.title}")
            lines.append("")
            content = self._get_final_content(chapter)
            lines.append(content)
            lines.append("")

        # Write to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{project.title}_{timestamp}.md"
        filepath = os.path.join(self.export_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return filepath

    async def export_epub(self, project_id: UUID) -> str:
        """Export project as EPUB file. Returns filepath."""
        project = await self._get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        chapters = await self._get_chapters(project_id)

        # Create EPUB book
        book = epub.EpubBook()
        book.set_identifier(str(project.id))
        book.set_title(project.title)
        book.set_language("zh")

        # Add chapters
        epub_chapters = []
        for idx, chapter in enumerate(chapters, 1):
            c = epub.EpubHtml()
            c.file_name = f"chap_{idx:02d}.xhtml"
            c.title = chapter.title

            content = self._get_final_content(chapter)
            c.content = f"<h1>{chapter.title}</h1>\n<p>{content}</p>"

            book.add_item(c)
            epub_chapters.append(c)

        # Define Table of Contents
        book.toc = epub_chapters

        # Add book to spine
        book.spine = ["nav"] + epub_chapters

        # Add navigation files
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        # Write to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{project.title}_{timestamp}.epub"
        filepath = os.path.join(self.export_dir, filename)

        epub.write_epub(filepath, book, {})

        return filepath
