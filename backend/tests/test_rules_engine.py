# backend/tests/test_rules_engine.py
import pytest
from app.engines.rules_engine import (
    RulesEngine,
    BASE_GUARDRAILS,
    GENRE_PROFILES,
    AUDIT_DIMENSIONS,
)


def test_base_guardrails_count():
    """Base guardrails should have ~25 rules."""
    assert len(BASE_GUARDRAILS) >= 20
    assert len(BASE_GUARDRAILS) <= 30


def test_base_guardrails_structure():
    """Each guardrail should have id, category, rule, description."""
    for g in BASE_GUARDRAILS:
        assert "id" in g
        assert "category" in g
        assert "rule" in g
        assert "description" in g


def test_genre_profiles_exist():
    """Should have xuanhuan, xianxia, urban presets."""
    assert "xuanhuan" in GENRE_PROFILES
    assert "xianxia" in GENRE_PROFILES
    assert "urban" in GENRE_PROFILES


def test_genre_profile_structure():
    """Each genre profile should have disabled_dimensions, taboos, settings."""
    for name, profile in GENRE_PROFILES.items():
        assert "disabled_dimensions" in profile
        assert "taboos" in profile
        assert "settings" in profile
        assert isinstance(profile["disabled_dimensions"], list)


def test_audit_dimensions_count():
    """Should have 33 audit dimensions across 6 categories."""
    assert len(AUDIT_DIMENSIONS) == 33
    categories = {d["category"] for d in AUDIT_DIMENSIONS}
    assert categories == {"consistency", "narrative", "character", "structure", "style", "engagement"}


def test_audit_dimension_structure():
    for d in AUDIT_DIMENSIONS:
        assert "id" in d
        assert "name" in d
        assert "category" in d
        assert "description" in d
        assert "is_deterministic" in d


def test_rules_engine_merge():
    """RulesEngine.merge() should combine 3 layers."""
    engine = RulesEngine()
    merged = engine.merge(
        genre="xuanhuan",
        book_rules={"custom_rules": [{"id": "custom_1", "rule": "No romance"}]},
    )
    # Should have base guardrails + genre taboos + custom rules
    assert len(merged["guardrails"]) >= 20
    assert len(merged["taboos"]) > 0
    assert any(r["id"] == "custom_1" for r in merged["custom_rules"])


def test_rules_engine_active_dimensions():
    """Active dimensions should exclude genre-disabled ones."""
    engine = RulesEngine()
    active = engine.get_active_dimensions(genre="xuanhuan")
    all_dims = engine.get_active_dimensions(genre=None)
    # xuanhuan should disable some dimensions
    assert len(active) <= len(all_dims)
    assert len(active) >= 28  # at most 5 disabled


def test_rules_engine_format_for_prompt():
    """format_for_prompt should return a formatted string."""
    engine = RulesEngine()
    merged = engine.merge(genre="xuanhuan")
    text = engine.format_for_prompt(merged)
    assert isinstance(text, str)
    assert len(text) > 100
    assert "基础护栏" in text or "guardrail" in text.lower()
