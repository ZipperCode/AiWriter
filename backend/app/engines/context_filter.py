"""Context Filter: POV-aware context assembly for the Writer agent."""

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.chapter import Chapter
from app.models.entity import Entity
from app.models.scene_card import SceneCard
from app.models.truth_file import TruthFile


class ContextFilter:
    """Assembles context for Writer, filtered by POV character's knowledge boundary."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def assemble_context(self, chapter_id: UUID, pov_character_id: UUID | None = None) -> dict:
        chapter = await self._get_chapter(chapter_id)
        if chapter is None:
            raise ValueError(f"Chapter {chapter_id} not found")
        project_id = chapter.project_id
        sections: dict[str, str] = {}
        story_bible = await self._get_truth_file_content(project_id, "story_bible")
        if story_bible:
            sections["story_bible"] = self._format_dict(story_bible)
        current_state = await self._get_truth_file_content(project_id, "current_state")
        if current_state:
            sections["current_state"] = self._format_dict(current_state)
        summaries = await self._get_chapter_summaries(project_id, chapter.sort_order, pov_character_id)
        if summaries:
            sections["chapter_summaries"] = summaries
        scene_cards = await self._get_scene_cards(chapter_id)
        if scene_cards:
            sections["scene_cards"] = scene_cards
        if pov_character_id:
            pov_state = await self._get_pov_state(pov_character_id)
            if pov_state:
                sections["pov_character"] = pov_state
        system_prompt = self._build_system_prompt(sections)
        user_prompt = self._build_user_prompt(chapter, sections)
        all_text = system_prompt + user_prompt
        context_tokens = int(len(all_text) * 1.5)
        return {"system_prompt": system_prompt, "user_prompt": user_prompt, "context_tokens": context_tokens, "sections": sections}

    async def _get_chapter(self, chapter_id: UUID) -> Chapter | None:
        stmt = select(Chapter).where(Chapter.id == chapter_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_truth_file_content(self, project_id: UUID, file_type: str) -> dict | None:
        stmt = select(TruthFile).where(TruthFile.project_id == project_id, TruthFile.file_type == file_type)
        result = await self.db.execute(stmt)
        tf = result.scalar_one_or_none()
        return tf.content if tf and tf.content else None

    async def _get_chapter_summaries(self, project_id: UUID, current_sort_order: int, pov_character_id: UUID | None) -> str:
        stmt = select(Chapter).where(Chapter.project_id == project_id, Chapter.sort_order < current_sort_order, Chapter.summary.isnot(None)).order_by(Chapter.sort_order)
        result = await self.db.execute(stmt)
        chapters = list(result.scalars().all())
        if not chapters:
            return ""
        if pov_character_id:
            chapters = [ch for ch in chapters if ch.pov_character_id == pov_character_id or ch.pov_character_id is None]
        lines = []
        for ch in chapters[-5:]:
            lines.append(f"[{ch.title}] {ch.summary}")
        return "\n".join(lines)

    async def _get_scene_cards(self, chapter_id: UUID) -> str:
        stmt = select(SceneCard).where(SceneCard.chapter_id == chapter_id).order_by(SceneCard.sort_order)
        result = await self.db.execute(stmt)
        cards = list(result.scalars().all())
        if not cards:
            return ""
        lines = []
        for card in cards:
            parts = [f"Scene {card.sort_order}"]
            if card.location:
                parts.append(f"Location: {card.location}")
            parts.append(f"Goal: {card.goal}")
            if card.conflict:
                parts.append(f"Conflict: {card.conflict}")
            if card.outcome:
                parts.append(f"Outcome: {card.outcome}")
            lines.append(" | ".join(parts))
        return "\n".join(lines)

    async def _get_pov_state(self, pov_character_id: UUID) -> str:
        stmt = select(Entity).where(Entity.id == pov_character_id)
        result = await self.db.execute(stmt)
        entity = result.scalar_one_or_none()
        if not entity:
            return ""
        parts = [f"POV: {entity.name} ({entity.entity_type})"]
        if entity.attributes:
            parts.append(f"Attributes: {self._format_dict(entity.attributes)}")
        if entity.knowledge_boundary:
            parts.append(f"Knowledge: {self._format_dict(entity.knowledge_boundary)}")
        return "\n".join(parts)

    def _build_system_prompt(self, sections: dict[str, str]) -> str:
        parts = ["You are a novel writer."]
        if "story_bible" in sections:
            parts.append(f"\n## World Setting\n{sections['story_bible']}")
        return "\n".join(parts)

    def _build_user_prompt(self, chapter: Chapter, sections: dict[str, str]) -> str:
        parts = [f"## Chapter: {chapter.title}"]
        if "current_state" in sections:
            parts.append(f"\n## Current State\n{sections['current_state']}")
        if "chapter_summaries" in sections:
            parts.append(f"\n## Previous Chapters\n{sections['chapter_summaries']}")
        if "scene_cards" in sections:
            parts.append(f"\n## Scene Cards\n{sections['scene_cards']}")
        if "pov_character" in sections:
            parts.append(f"\n## POV Character\n{sections['pov_character']}")
        parts.append("\nPlease write this chapter.")
        return "\n".join(parts)

    @staticmethod
    def _format_dict(d: dict) -> str:
        return ", ".join(f"{k}: {v}" for k, v in d.items())
