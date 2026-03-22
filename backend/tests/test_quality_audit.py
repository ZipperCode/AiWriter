# backend/tests/test_quality_audit.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from app.engines.quality_audit import AuditRunner, AuditReport, DimensionResult
from app.engines.de_ai import DeAIEngine


def test_audit_report_pass_rate():
    """Pass rate = dimensions with score >= 7 / total enabled dimensions."""
    results = [
        DimensionResult(dimension_id=i, name=f"dim_{i}", category="test", score=8.0, severity="pass", message="ok", evidence=[])
        for i in range(1, 29)
    ]
    # Add 5 low-scoring dimensions
    results.extend([
        DimensionResult(dimension_id=29, name="dim_29", category="test", score=3.0, severity="error", message="bad", evidence=[]),
        DimensionResult(dimension_id=30, name="dim_30", category="test", score=5.0, severity="warning", message="meh", evidence=[]),
        DimensionResult(dimension_id=31, name="dim_31", category="test", score=6.0, severity="warning", message="meh", evidence=[]),
        DimensionResult(dimension_id=32, name="dim_32", category="test", score=2.0, severity="error", message="bad", evidence=[]),
        DimensionResult(dimension_id=33, name="dim_33", category="test", score=0.0, severity="blocking", message="fatal", evidence=[]),
    ])
    report = AuditReport(results=results)
    # 28 pass out of 33 = ~84.8%
    assert abs(report.pass_rate - 28 / 33) < 0.01
    assert report.has_blocking is True
    assert report.recommendation == "revise"  # has blocking


def test_audit_report_rework_threshold():
    """Pass rate < 60% should trigger rework recommendation."""
    results = [
        DimensionResult(dimension_id=i, name=f"dim_{i}", category="test",
                        score=3.0 if i <= 20 else 8.0, severity="error" if i <= 20 else "pass",
                        message="x", evidence=[])
        for i in range(1, 34)
    ]
    report = AuditReport(results=results)
    # 13 pass out of 33 = ~39.4%
    assert report.pass_rate < 0.6
    assert report.recommendation == "rework"


def test_audit_report_pass_threshold():
    """Pass rate >= 85% and no blocking should pass."""
    results = [
        DimensionResult(dimension_id=i, name=f"dim_{i}", category="test",
                        score=9.0, severity="pass", message="ok", evidence=[])
        for i in range(1, 34)
    ]
    report = AuditReport(results=results)
    assert report.pass_rate >= 0.85
    assert report.has_blocking is False
    assert report.recommendation == "pass"


def test_deterministic_ai_trace(de_ai_engine):
    """Deterministic check #26: AI trace detection."""
    runner = AuditRunner(de_ai_engine=de_ai_engine)
    text = "他不禁缓缓地叹了口气，眼中闪过一丝复杂的神色。空气仿佛凝固了。"
    result = runner.check_ai_traces(text)
    assert result.dimension_id == 26
    assert result.score < 7  # Should flag AI traces


def test_deterministic_ai_trace_clean(de_ai_engine):
    """Clean text should pass AI trace check."""
    runner = AuditRunner(de_ai_engine=de_ai_engine)
    text = "老张蹲在门槛上抽旱烟，烟雾飘过他布满皱纹的脸。" * 30
    result = runner.check_ai_traces(text)
    assert result.score >= 7


def test_deterministic_repetition():
    """Deterministic check #27: repetition detection."""
    runner = AuditRunner()
    text = "他走了过去。他走了过去。他又走了过去。其他人也走了过去。大家都走了过去。"
    result = runner.check_repetition(text)
    assert result.dimension_id == 27
    assert result.score < 7


def test_deterministic_repetition_clean():
    """Non-repetitive text should pass."""
    runner = AuditRunner()
    text = "晨光透过树叶的缝隙洒在石阶上。远处传来鸟鸣声。山风带着松脂的清香拂过面庞。溪水潺潺流过脚边的卵石。" * 5
    result = runner.check_repetition(text)
    assert result.score >= 7


def test_deterministic_banned_words(de_ai_engine):
    """Deterministic check #28: banned word/pattern detection."""
    runner = AuditRunner(de_ai_engine=de_ai_engine)
    text = "他的眼中闪过一丝不易察觉的光芒。" * 3
    result = runner.check_banned_words(text)
    assert result.dimension_id == 28
    assert result.score < 7


def test_run_deterministic_checks(de_ai_engine):
    """run_deterministic_checks should return results for all deterministic dimensions."""
    runner = AuditRunner(de_ai_engine=de_ai_engine)
    text = "他不禁缓缓走向前方。" * 20
    results = runner.run_deterministic_checks(text)
    dim_ids = {r.dimension_id for r in results}
    assert 26 in dim_ids  # AI trace
    assert 27 in dim_ids  # repetition
    assert 28 in dim_ids  # banned words


@pytest.fixture
def de_ai_engine():
    return DeAIEngine()
