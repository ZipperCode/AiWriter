# backend/tests/test_integration_iter3.py
"""Integration tests for iteration 3: rules + de-AI + audit + pacing working together."""
import pytest
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from app.engines.rules_engine import RulesEngine, AUDIT_DIMENSIONS, BASE_GUARDRAILS
from app.engines.de_ai import DeAIEngine
from app.engines.quality_audit import AuditRunner, AuditReport, DimensionResult
from app.engines.pacing_control import PacingController
from app.models.project import Project
from app.models.volume import Volume
from app.models.chapter import Chapter
from app.models.book_rules import BookRules
from app.models.pacing_meta import PacingMeta


def test_rules_deai_integration():
    """Rules engine format + De-AI format should be combinable for Writer prompt."""
    rules_engine = RulesEngine()
    de_ai = DeAIEngine()

    merged = rules_engine.merge(genre="xuanhuan")
    rules_text = rules_engine.format_for_prompt(merged)
    deai_text = de_ai.format_for_prompt(top_words=50, top_patterns=20)

    combined = f"{rules_text}\n\n{deai_text}"
    assert "基础护栏" in combined
    assert "禁止" in combined
    assert len(combined) > 500


def test_audit_with_genre_dimensions():
    """Audit runner should respect genre-disabled dimensions."""
    rules_engine = RulesEngine()
    active = rules_engine.get_active_dimensions(genre="xuanhuan")

    # xuanhuan disables dialogue_narration_ratio
    active_names = {d["name"] for d in active}
    assert "dialogue_narration_ratio" not in active_names
    assert len(active) == 32  # 33 - 1 disabled


def test_deterministic_audit_full_flow():
    """Full deterministic audit flow: detect -> score -> report -> recommend."""
    de_ai = DeAIEngine()
    runner = AuditRunner(de_ai_engine=de_ai)

    # AI-heavy text
    ai_text = "他不禁缓缓叹了口气，眼中闪过一丝复杂的神色。" * 30
    results = runner.run_deterministic_checks(ai_text)

    report = AuditReport(results=results)
    assert report.pass_rate < 1.0  # Should have some failures
    assert isinstance(report.recommendation, str)
    assert report.recommendation in ("pass", "revise", "rework")


async def test_pacing_with_book_rules(db_session: AsyncSession):
    """Pacing controller should work alongside book rules."""
    project = Project(title="Test", genre="xuanhuan", status="active", settings={})
    db_session.add(project)
    await db_session.flush()

    rules = BookRules(
        project_id=project.id,
        base_guardrails={},
        genre_profile={"name": "xuanhuan"},
        custom_rules={},
    )
    db_session.add(rules)

    volume = Volume(project_id=project.id, title="V1", objective="test objective", sort_order=1)
    db_session.add(volume)
    await db_session.flush()

    for i in range(1, 6):
        ch = Chapter(
            project_id=project.id, volume_id=volume.id,
            title=f"Ch{i}", sort_order=i, status="final",
        )
        db_session.add(ch)
        await db_session.flush()
        pm = PacingMeta(
            chapter_id=ch.id,
            quest_ratio=0.6, fire_ratio=0.2, constellation_ratio=0.2,
            highlight_count=1, highlight_types=["装逼打脸"],
            tension_level=0.5, strand_tags=["quest", "fire"],
        )
        db_session.add(pm)
    await db_session.flush()

    ctrl = PacingController(db_session)
    analysis = await ctrl.analyze_pacing(project.id)
    assert len(analysis.chapter_pacing) == 5

    violations = await ctrl.check_red_lines(project.id)
    # Should not have violations with balanced pacing
    quest_violations = [v for v in violations if v.rule == "quest_continuous_limit"]
    assert len(quest_violations) == 0

    suggestion = await ctrl.suggest_next_chapter(project.id)
    assert len(suggestion.recommended_strands) > 0
