"""Tests for human-in-the-loop breakpoints."""

from uuid import uuid4

from app.orchestration.human_loop import HumanLoopDecision, HumanLoopManager, HumanLoopPoint


def test_human_loop_point_creation():
    """Should create a HumanLoopPoint with valid config."""
    point = HumanLoopPoint(trigger="always", timeout_hours=24.0, fallback="pause")
    assert point.trigger == "always"
    assert point.timeout_hours == 24.0
    assert point.fallback == "pause"


def test_human_loop_point_never_trigger():
    """'never' trigger should always return False for should_pause."""
    point = HumanLoopPoint(trigger="never")
    assert point.should_pause(score=0.3, is_first_run=True) is False


def test_human_loop_point_always_trigger():
    """'always' trigger should always return True."""
    point = HumanLoopPoint(trigger="always")
    assert point.should_pause(score=0.9, is_first_run=False) is True


def test_human_loop_point_on_low_score():
    """'on_low_score' should pause when score < 0.7."""
    point = HumanLoopPoint(trigger="on_low_score")
    assert point.should_pause(score=0.5, is_first_run=False) is True
    assert point.should_pause(score=0.8, is_first_run=False) is False


def test_human_loop_point_on_first_run():
    """'on_first_run' should pause only on first run."""
    point = HumanLoopPoint(trigger="on_first_run")
    assert point.should_pause(score=0.9, is_first_run=True) is True
    assert point.should_pause(score=0.9, is_first_run=False) is False


def test_human_loop_manager_submit_decision():
    """Should store and retrieve human decisions."""
    manager = HumanLoopManager()
    loop_id = uuid4()
    manager.create_pending(loop_id, node_name="auditor", data={"score": 0.5})

    assert manager.is_pending(loop_id) is True

    manager.submit_decision(
        loop_id,
        HumanLoopDecision(action="approve", content=None),
    )
    assert manager.is_pending(loop_id) is False
    decision = manager.get_decision(loop_id)
    assert decision is not None
    assert decision.action == "approve"
