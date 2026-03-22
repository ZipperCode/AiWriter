# backend/tests/test_schemas_iter3.py
import pytest
from uuid import uuid4
from app.schemas.rules import (
    BookRulesResponse, BookRulesUpdate, GenreProfileResponse,
    MergedRulesResponse, GenreListResponse,
)
from app.schemas.audit import (
    AuditDimensionScore, AuditReportResponse,
    DimensionListResponse,
)
from app.schemas.pacing import (
    PacingAnalysisResponse, RedLineViolationResponse,
    PacingSuggestionResponse, ChapterPacingResponse,
)


def test_book_rules_response():
    r = BookRulesResponse(
        id=uuid4(), project_id=uuid4(),
        base_guardrails={"rules": []}, genre_profile={"name": "xuanhuan"},
        custom_rules={"rules": []},
    )
    assert r.project_id is not None


def test_book_rules_update():
    u = BookRulesUpdate(
        base_guardrails={"rules": [{"id": "bg_01"}]},
        genre_profile={"name": "xianxia"},
    )
    assert u.genre_profile["name"] == "xianxia"


def test_genre_profile_response():
    g = GenreProfileResponse(name="xuanhuan", zh_name="玄幻", disabled_dimensions=["dim1"], taboos=[], settings={})
    assert g.name == "xuanhuan"


def test_genre_list_response():
    gl = GenreListResponse(genres=[
        GenreProfileResponse(name="xuanhuan", zh_name="玄幻", disabled_dimensions=[], taboos=[], settings={}),
    ])
    assert len(gl.genres) == 1


def test_merged_rules_response():
    m = MergedRulesResponse(
        guardrails=[], taboos=[], custom_rules=[],
        settings={}, disabled_dimensions=[],
        prompt_text="## Rules",
    )
    assert "Rules" in m.prompt_text


def test_audit_dimension_score():
    s = AuditDimensionScore(
        dimension_id=1, name="test", zh_name="测试",
        category="style", score=8.5, severity="pass",
        message="ok", evidence=[],
    )
    assert s.severity == "pass"


def test_audit_report_response():
    r = AuditReportResponse(
        chapter_id=uuid4(), mode="full",
        scores=[], pass_rate=0.85,
        has_blocking=False, recommendation="pass",
        issues=[],
    )
    assert r.recommendation == "pass"


def test_dimension_list_response():
    d = DimensionListResponse(dimensions=[], total=33, active=30)
    assert d.active < d.total


def test_chapter_pacing_response():
    cp = ChapterPacingResponse(
        chapter_id=uuid4(), sort_order=1,
        quest_ratio=0.6, fire_ratio=0.2, constellation_ratio=0.2,
        highlight_count=1, highlight_types=["装逼打脸"],
        tension_level=0.5, strand_tags=["quest"],
    )
    assert cp.quest_ratio == 0.6


def test_pacing_analysis_response():
    pa = PacingAnalysisResponse(
        chapter_pacing=[], avg_quest_ratio=0.6,
        avg_fire_ratio=0.2, avg_constellation_ratio=0.2,
        total_highlights=10, avg_tension=0.5,
        violations=[],
    )
    assert pa.avg_quest_ratio == 0.6


def test_red_line_violation_response():
    v = RedLineViolationResponse(
        rule="quest_continuous_limit",
        message="Too many quest chapters",
        severity="warning",
        affected_chapters=[1, 2, 3, 4, 5, 6],
    )
    assert v.severity == "warning"


def test_pacing_suggestion_response():
    s = PacingSuggestionResponse(
        recommended_strands=["fire", "constellation"],
        recommended_highlights=["装逼打脸"],
        tension_suggestion="Raise tension",
        target_ratios={"quest": 0.6},
    )
    assert "fire" in s.recommended_strands
