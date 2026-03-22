# backend/tests/test_pacing_control.py
import pytest
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from app.engines.pacing_control import PacingController, PacingAnalysis, RedLineViolation, PacingSuggestion
from app.models.project import Project
from app.models.volume import Volume
from app.models.chapter import Chapter
from app.models.pacing_meta import PacingMeta


async def _setup_pacing_data(db: AsyncSession, num_chapters: int = 6):
    """Create project with N chapters and pacing meta."""
    project = Project(title="Test Novel", genre="xuanhuan", status="active", settings={})
    db.add(project)
    await db.flush()

    volume = Volume(project_id=project.id, title="V1", objective="Test", sort_order=1)
    db.add(volume)
    await db.flush()

    chapters = []
    for i in range(1, num_chapters + 1):
        ch = Chapter(
            project_id=project.id, volume_id=volume.id,
            title=f"Chapter {i}", sort_order=i, status="final",
            summary=f"Summary of chapter {i}",
        )
        db.add(ch)
        await db.flush()
        chapters.append(ch)

    return project, volume, chapters


async def test_analyze_pacing_basic(db_session: AsyncSession):
    """analyze_pacing should return PacingAnalysis for a project."""
    project, volume, chapters = await _setup_pacing_data(db_session)

    # Add pacing meta for chapters
    for i, ch in enumerate(chapters):
        pm = PacingMeta(
            chapter_id=ch.id,
            quest_ratio=0.6, fire_ratio=0.2, constellation_ratio=0.2,
            highlight_count=1, highlight_types=["装逼打脸"],
            tension_level=0.5 + i * 0.05, strand_tags=["quest"],
        )
        db_session.add(pm)
    await db_session.flush()

    ctrl = PacingController(db_session)
    analysis = await ctrl.analyze_pacing(project.id)
    assert isinstance(analysis, PacingAnalysis)
    assert len(analysis.chapter_pacing) == 6
    assert analysis.avg_quest_ratio > 0


async def test_check_red_lines_quest_limit(db_session: AsyncSession):
    """Quest strand continuous > 5 chapters should trigger red line."""
    project, volume, chapters = await _setup_pacing_data(db_session, num_chapters=7)

    # All 7 chapters are quest-only (no fire or constellation)
    for ch in chapters:
        pm = PacingMeta(
            chapter_id=ch.id,
            quest_ratio=1.0, fire_ratio=0.0, constellation_ratio=0.0,
            highlight_count=1, highlight_types=["越级反杀"],
            tension_level=0.5, strand_tags=["quest"],
        )
        db_session.add(pm)
    await db_session.flush()

    ctrl = PacingController(db_session)
    violations = await ctrl.check_red_lines(project.id)
    assert len(violations) > 0
    assert any(v.rule == "quest_continuous_limit" for v in violations)


async def test_check_red_lines_fire_gap(db_session: AsyncSession):
    """Fire strand gap > 3 chapters should trigger red line."""
    project, volume, chapters = await _setup_pacing_data(db_session, num_chapters=5)

    # 5 chapters with no fire strand
    for ch in chapters:
        pm = PacingMeta(
            chapter_id=ch.id,
            quest_ratio=0.8, fire_ratio=0.0, constellation_ratio=0.2,
            highlight_count=1, highlight_types=["扮猪吃虎"],
            tension_level=0.5, strand_tags=["quest", "constellation"],
        )
        db_session.add(pm)
    await db_session.flush()

    ctrl = PacingController(db_session)
    violations = await ctrl.check_red_lines(project.id)
    assert any(v.rule == "fire_gap_limit" for v in violations)


async def test_check_red_lines_emotion_low(db_session: AsyncSession):
    """Tension level low for 4+ consecutive chapters should trigger red line."""
    project, volume, chapters = await _setup_pacing_data(db_session, num_chapters=5)

    for ch in chapters:
        pm = PacingMeta(
            chapter_id=ch.id,
            quest_ratio=0.6, fire_ratio=0.2, constellation_ratio=0.2,
            highlight_count=0, highlight_types=[],
            tension_level=0.1, strand_tags=["quest"],
        )
        db_session.add(pm)
    await db_session.flush()

    ctrl = PacingController(db_session)
    violations = await ctrl.check_red_lines(project.id)
    assert any(v.rule == "emotion_low_limit" for v in violations)


async def test_check_coolpoint_density(db_session: AsyncSession):
    """Cool-point check: every chapter should have >= 1 cool-point."""
    project, volume, chapters = await _setup_pacing_data(db_session, num_chapters=5)

    # Give first 3 chapters cool-points, last 2 have none
    for i, ch in enumerate(chapters):
        pm = PacingMeta(
            chapter_id=ch.id,
            quest_ratio=0.6, fire_ratio=0.2, constellation_ratio=0.2,
            highlight_count=1 if i < 3 else 0,
            highlight_types=["装逼打脸"] if i < 3 else [],
            tension_level=0.5, strand_tags=["quest"],
        )
        db_session.add(pm)
    await db_session.flush()

    ctrl = PacingController(db_session)
    violations = await ctrl.check_red_lines(project.id)
    assert any(v.rule == "coolpoint_per_chapter" for v in violations)


async def test_suggest_next_chapter(db_session: AsyncSession):
    """suggest_next_chapter should return a PacingSuggestion."""
    project, volume, chapters = await _setup_pacing_data(db_session)

    for i, ch in enumerate(chapters):
        pm = PacingMeta(
            chapter_id=ch.id,
            quest_ratio=0.8, fire_ratio=0.1, constellation_ratio=0.1,
            highlight_count=1, highlight_types=["越级反杀"],
            tension_level=0.5, strand_tags=["quest"],
        )
        db_session.add(pm)
    await db_session.flush()

    ctrl = PacingController(db_session)
    suggestion = await ctrl.suggest_next_chapter(project.id)
    assert isinstance(suggestion, PacingSuggestion)
    assert suggestion.recommended_strands  # Should suggest adding fire/constellation
    assert suggestion.tension_suggestion  # Should have tension advice


def test_coolpoint_patterns():
    """Should recognize 6 cool-point patterns."""
    from app.engines.pacing_control import COOLPOINT_PATTERNS
    assert len(COOLPOINT_PATTERNS) == 6
    expected = {"装逼打脸", "扮猪吃虎", "越级反杀", "打脸权威", "反派翻车", "甜蜜超预期"}
    assert set(COOLPOINT_PATTERNS.keys()) == expected
