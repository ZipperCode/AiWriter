# backend/app/engines/pacing_control.py
"""Pacing Controller: Strand Weave + Red Lines + Cool-Point Tracking.

Three strands: Quest(60%) / Fire(20%) / Constellation(20%)

Red line rules:
- Quest continuous <= 5 chapters
- Fire gap <= 3 chapters
- Emotion low <= 4 consecutive chapters (triggers turning point)
- Every chapter >= 1 cool-point

Cool-point patterns (6):
  装逼打脸 / 扮猪吃虎 / 越级反杀 / 打脸权威 / 反派翻车 / 甜蜜超预期

Targets:
- Per chapter: >= 1 cool-point
- Per 5 chapters: >= 1 combo
- Per 10 chapters: >= 1 milestone victory
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.chapter import Chapter
from app.models.pacing_meta import PacingMeta

# 6 Cool-point patterns
COOLPOINT_PATTERNS: dict[str, str] = {
    "装逼打脸": "主角展示实力打脸质疑者",
    "扮猪吃虎": "主角隐藏实力后突然爆发",
    "越级反杀": "主角以弱胜强逆转战局",
    "打脸权威": "主角挑战并击败高位者",
    "反派翻车": "反派阴谋被揭穿或自食其果",
    "甜蜜超预期": "感情线或奖励超出期待",
}

# Strand ideal ratios
IDEAL_QUEST_RATIO = 0.6
IDEAL_FIRE_RATIO = 0.2
IDEAL_CONSTELLATION_RATIO = 0.2

# Red line thresholds
MAX_QUEST_CONTINUOUS = 5
MAX_FIRE_GAP = 3
MAX_EMOTION_LOW_CONTINUOUS = 4
EMOTION_LOW_THRESHOLD = 0.3
MIN_COOLPOINT_PER_CHAPTER = 1


@dataclass
class ChapterPacing:
    """Pacing data for a single chapter."""
    chapter_id: UUID
    sort_order: int
    quest_ratio: float
    fire_ratio: float
    constellation_ratio: float
    highlight_count: int
    highlight_types: list[str]
    tension_level: float
    strand_tags: list[str]


@dataclass
class PacingAnalysis:
    """Overall pacing analysis for a project."""
    chapter_pacing: list[ChapterPacing] = field(default_factory=list)
    avg_quest_ratio: float = 0.0
    avg_fire_ratio: float = 0.0
    avg_constellation_ratio: float = 0.0
    total_highlights: int = 0
    avg_tension: float = 0.0


@dataclass
class RedLineViolation:
    """A pacing red line violation."""
    rule: str
    message: str
    severity: str  # warning / error
    affected_chapters: list[int] = field(default_factory=list)  # sort_orders


@dataclass
class PacingSuggestion:
    """Pacing suggestion for the next chapter."""
    recommended_strands: list[str] = field(default_factory=list)
    recommended_highlights: list[str] = field(default_factory=list)
    tension_suggestion: str = ""
    target_ratios: dict[str, float] = field(default_factory=dict)


class PacingController:
    """Controls story pacing using Strand Weave methodology."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _load_pacing_data(self, project_id: UUID) -> list[ChapterPacing]:
        """Load pacing meta for all chapters in a project, ordered by sort_order."""
        stmt = (
            select(Chapter, PacingMeta)
            .outerjoin(PacingMeta, Chapter.id == PacingMeta.chapter_id)
            .where(Chapter.project_id == project_id)
            .order_by(Chapter.sort_order)
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        data: list[ChapterPacing] = []
        for ch, pm in rows:
            if pm is None:
                continue
            data.append(ChapterPacing(
                chapter_id=ch.id,
                sort_order=ch.sort_order,
                quest_ratio=pm.quest_ratio or 0.0,
                fire_ratio=pm.fire_ratio or 0.0,
                constellation_ratio=pm.constellation_ratio or 0.0,
                highlight_count=pm.highlight_count,
                highlight_types=pm.highlight_types or [],
                tension_level=pm.tension_level or 0.0,
                strand_tags=pm.strand_tags or [],
            ))
        return data

    async def analyze_pacing(self, project_id: UUID) -> PacingAnalysis:
        """Analyze overall pacing for a project."""
        data = await self._load_pacing_data(project_id)
        if not data:
            return PacingAnalysis()

        n = len(data)
        analysis = PacingAnalysis(
            chapter_pacing=data,
            avg_quest_ratio=sum(d.quest_ratio for d in data) / n,
            avg_fire_ratio=sum(d.fire_ratio for d in data) / n,
            avg_constellation_ratio=sum(d.constellation_ratio for d in data) / n,
            total_highlights=sum(d.highlight_count for d in data),
            avg_tension=sum(d.tension_level for d in data) / n,
        )
        return analysis

    async def check_red_lines(self, project_id: UUID) -> list[RedLineViolation]:
        """Check all pacing red line rules."""
        data = await self._load_pacing_data(project_id)
        if not data:
            return []

        violations: list[RedLineViolation] = []

        # Rule 1: Quest continuous <= 5 chapters
        quest_run = 0
        quest_run_start = 0
        for i, d in enumerate(data):
            if "quest" in d.strand_tags and "fire" not in d.strand_tags and "constellation" not in d.strand_tags:
                if quest_run == 0:
                    quest_run_start = i
                quest_run += 1
            else:
                quest_run = 0

            if quest_run > MAX_QUEST_CONTINUOUS:
                affected = [data[j].sort_order for j in range(quest_run_start, i + 1)]
                violations.append(RedLineViolation(
                    rule="quest_continuous_limit",
                    message=f"Quest strand continuous for {quest_run} chapters (limit: {MAX_QUEST_CONTINUOUS})",
                    severity="warning",
                    affected_chapters=affected,
                ))
                break

        # Rule 2: Fire gap <= 3 chapters
        fire_gap = 0
        for d in data:
            if d.fire_ratio > 0.05 or "fire" in d.strand_tags:
                fire_gap = 0
            else:
                fire_gap += 1

            if fire_gap > MAX_FIRE_GAP:
                affected = [data[j].sort_order for j in range(len(data) - fire_gap, len(data))]
                violations.append(RedLineViolation(
                    rule="fire_gap_limit",
                    message=f"Fire strand absent for {fire_gap} chapters (limit: {MAX_FIRE_GAP})",
                    severity="warning",
                    affected_chapters=affected,
                ))
                break

        # Rule 3: Emotion low <= 4 consecutive chapters
        low_tension_run = 0
        for i, d in enumerate(data):
            if d.tension_level < EMOTION_LOW_THRESHOLD:
                low_tension_run += 1
            else:
                low_tension_run = 0

            if low_tension_run >= MAX_EMOTION_LOW_CONTINUOUS:
                affected = [data[j].sort_order for j in range(i - low_tension_run + 1, i + 1)]
                violations.append(RedLineViolation(
                    rule="emotion_low_limit",
                    message=f"Low tension for {low_tension_run} consecutive chapters (threshold: {EMOTION_LOW_THRESHOLD})",
                    severity="error",
                    affected_chapters=affected,
                ))
                break

        # Rule 4: Every chapter >= 1 cool-point
        no_coolpoint = [d.sort_order for d in data if d.highlight_count < MIN_COOLPOINT_PER_CHAPTER]
        if no_coolpoint:
            violations.append(RedLineViolation(
                rule="coolpoint_per_chapter",
                message=f"{len(no_coolpoint)} chapters have no cool-points",
                severity="warning",
                affected_chapters=no_coolpoint,
            ))

        # Rule 5: Every 5 chapters >= 1 combo (2+ cool-points in one chapter)
        for start in range(0, len(data), 5):
            chunk = data[start:start + 5]
            if len(chunk) >= 5:
                has_combo = any(d.highlight_count >= 2 for d in chunk)
                if not has_combo:
                    violations.append(RedLineViolation(
                        rule="combo_per_5_chapters",
                        message=f"No combo (2+ cool-points) in chapters {chunk[0].sort_order}-{chunk[-1].sort_order}",
                        severity="warning",
                        affected_chapters=[d.sort_order for d in chunk],
                    ))

        return violations

    async def suggest_next_chapter(self, project_id: UUID) -> PacingSuggestion:
        """Suggest pacing direction for the next chapter."""
        data = await self._load_pacing_data(project_id)

        suggestion = PacingSuggestion(
            target_ratios={
                "quest": IDEAL_QUEST_RATIO,
                "fire": IDEAL_FIRE_RATIO,
                "constellation": IDEAL_CONSTELLATION_RATIO,
            },
        )

        if not data:
            suggestion.recommended_strands = ["quest", "fire"]
            suggestion.tension_suggestion = "Opening chapter: establish core conflict with moderate tension."
            return suggestion

        # Analyze recent trends (last 5 chapters)
        recent = data[-5:]
        avg_quest = sum(d.quest_ratio for d in recent) / len(recent)
        avg_fire = sum(d.fire_ratio for d in recent) / len(recent)
        avg_constellation = sum(d.constellation_ratio for d in recent) / len(recent)
        avg_tension = sum(d.tension_level for d in recent) / len(recent)

        # Recommend underrepresented strands
        strands = []
        if avg_fire < 0.15:
            strands.append("fire")
        if avg_constellation < 0.15:
            strands.append("constellation")
        if avg_quest < 0.5:
            strands.append("quest")
        if not strands:
            strands = ["quest"]
        suggestion.recommended_strands = strands

        # Tension suggestion
        if avg_tension < 0.3:
            suggestion.tension_suggestion = "Tension has been low recently. Consider a major conflict or turning point."
        elif avg_tension > 0.8:
            suggestion.tension_suggestion = "Tension is very high. Consider a brief relief before next escalation."
        else:
            suggestion.tension_suggestion = "Tension is balanced. Continue gradual escalation."

        # Highlight suggestions based on what hasn't been used recently
        recent_types = set()
        for d in recent:
            recent_types.update(d.highlight_types)
        unused = [p for p in COOLPOINT_PATTERNS if p not in recent_types]
        suggestion.recommended_highlights = unused[:3] if unused else list(COOLPOINT_PATTERNS.keys())[:2]

        return suggestion
