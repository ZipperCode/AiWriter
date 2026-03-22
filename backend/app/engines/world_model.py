"""World Model Engine: entity matching (Aho-Corasick) + extraction (jieba)."""

from uuid import UUID

import ahocorasick
import jieba
import jieba.posseg as pseg
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity import Entity


class WorldModelEngine:
    """Manages entity extraction and real-time text matching."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._automaton_cache: dict[UUID, ahocorasick.Automaton] = {}

    async def build_automaton(self, project_id: UUID) -> ahocorasick.Automaton:
        """Build an Aho-Corasick automaton from all entities in a project."""
        stmt = select(Entity).where(Entity.project_id == project_id)
        result = await self.db.execute(stmt)
        entities = list(result.scalars().all())
        automaton = ahocorasick.Automaton()
        for entity in entities:
            automaton.add_word(entity.name, (str(entity.id), entity.name, entity.name))
            for alias in entity.aliases:
                if alias:
                    automaton.add_word(alias, (str(entity.id), entity.name, alias))
        automaton.make_automaton()
        self._automaton_cache[project_id] = automaton
        return automaton

    async def match_entities(self, text: str, project_id: UUID) -> list[dict]:
        """Match entities in text using Aho-Corasick automaton."""
        if not text:
            return []
        automaton = self._automaton_cache.get(project_id)
        if automaton is None:
            automaton = await self.build_automaton(project_id)
        if not automaton:
            return []
        seen: set[str] = set()
        matches: list[dict] = []
        for end_pos, (entity_id_str, name, matched_text) in automaton.iter(text):
            key = f"{entity_id_str}:{matched_text}"
            if key not in seen:
                seen.add(key)
                matches.append({
                    "entity_id": UUID(entity_id_str),
                    "name": name,
                    "matched_text": matched_text,
                    "position": end_pos - len(matched_text) + 1,
                })
        return matches

    async def extract_entities_jieba(self, text: str) -> list[dict]:
        """Extract candidate entities from text using jieba POS tagging."""
        if not text:
            return []
        interesting_flags = {"nr", "ns", "nt", "nz"}
        candidates: list[dict] = []
        seen: set[str] = set()
        for word, flag in pseg.cut(text):
            if flag in interesting_flags and word not in seen and len(word) >= 2:
                seen.add(word)
                candidates.append({"text": word, "flag": flag})
        return candidates

    def invalidate_cache(self, project_id: UUID) -> None:
        """Clear the automaton cache for a project."""
        self._automaton_cache.pop(project_id, None)
