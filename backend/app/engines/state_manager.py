"""State Manager: truth file CRUD with atomic versioning and history."""

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.truth_file import TruthFile, TruthFileHistory


class StateManager:
    """Manages the 10 truth files with version control."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_truth_file(self, project_id: UUID, file_type: str) -> TruthFile | None:
        stmt = select(TruthFile).where(TruthFile.project_id == project_id, TruthFile.file_type == file_type)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_truth_files(self, project_id: UUID) -> list[TruthFile]:
        stmt = select(TruthFile).where(TruthFile.project_id == project_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_truth_file(self, project_id: UUID, file_type: str, diff: dict, chapter_id: UUID | None = None) -> TruthFile:
        """Atomic update: save current version to history, apply diff, bump version."""
        tf = await self.get_truth_file(project_id, file_type)
        if tf is None:
            raise ValueError(f"Truth file '{file_type}' not found for project {project_id}")
        history = TruthFileHistory(truth_file_id=tf.id, version=tf.version, content=tf.content, changed_by_chapter_id=chapter_id)
        self.db.add(history)
        tf.content = diff
        tf.version += 1
        tf.updated_by_chapter_id = chapter_id
        await self.db.flush()
        return tf

    async def get_history(self, project_id: UUID, file_type: str) -> list[TruthFileHistory]:
        tf = await self.get_truth_file(project_id, file_type)
        if tf is None:
            return []
        stmt = select(TruthFileHistory).where(TruthFileHistory.truth_file_id == tf.id).order_by(TruthFileHistory.version)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_truth_file_at_version(self, project_id: UUID, file_type: str, version: int) -> TruthFileHistory | None:
        tf = await self.get_truth_file(project_id, file_type)
        if tf is None:
            return None
        stmt = select(TruthFileHistory).where(TruthFileHistory.truth_file_id == tf.id, TruthFileHistory.version == version)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
