# backend/tests/test_de_ai.py
import pytest
from app.engines.de_ai import DeAIEngine


def test_fatigue_words_count():
    """Should have 200+ fatigue words."""
    engine = DeAIEngine()
    words = engine.get_fatigue_words()
    assert len(words) >= 200


def test_fatigue_words_are_strings():
    engine = DeAIEngine()
    for word in engine.get_fatigue_words():
        assert isinstance(word, str)
        assert len(word) > 0


def test_banned_patterns_count():
    """Should have 30+ banned patterns."""
    engine = DeAIEngine()
    patterns = engine.get_banned_patterns()
    assert len(patterns) >= 30


def test_detect_fatigue_word():
    """detect() should find fatigue words in text."""
    engine = DeAIEngine()
    # "不禁" and "缓缓" are common AI fatigue words
    text = "他不禁缓缓地点了点头，眼中闪过一丝复杂的神色。"
    traces = engine.detect(text)
    assert len(traces) > 0
    assert any(t["type"] == "fatigue_word" for t in traces)


def test_detect_banned_pattern():
    """detect() should find banned sentence patterns."""
    engine = DeAIEngine()
    text = "他的眼神中闪过一丝不易察觉的光芒，嘴角微微上扬，露出一个意味深长的微笑。"
    traces = engine.detect(text)
    pattern_traces = [t for t in traces if t["type"] == "banned_pattern"]
    assert len(pattern_traces) > 0


def test_detect_clean_text():
    """Clean text should have zero or very few traces."""
    engine = DeAIEngine()
    text = "老张蹲在门槛上抽旱烟，烟雾飘过他布满皱纹的脸，他咂了咂嘴说：'今年雨水少。'"
    traces = engine.detect(text)
    assert len(traces) <= 1  # Clean human-like text


def test_detect_returns_positions():
    """Each trace should include position info."""
    engine = DeAIEngine()
    text = "他不禁缓缓地叹了口气。"
    traces = engine.detect(text)
    for t in traces:
        assert "type" in t
        assert "matched" in t
        assert "start" in t
        assert "end" in t


def test_get_fatigue_density():
    """get_fatigue_density should return traces per 1000 chars."""
    engine = DeAIEngine()
    text = "他不禁缓缓地叹了口气。" * 50  # ~500 chars
    density = engine.get_fatigue_density(text)
    assert isinstance(density, float)
    assert density > 0


def test_format_for_prompt():
    """format_for_prompt should return top N fatigue words + patterns for prompt."""
    engine = DeAIEngine()
    text = engine.format_for_prompt(top_words=50, top_patterns=20)
    assert isinstance(text, str)
    assert len(text) > 100
    assert "禁止" in text or "不使用" in text
