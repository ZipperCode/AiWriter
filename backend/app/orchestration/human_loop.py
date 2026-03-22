"""Human-in-the-loop breakpoint management."""

from dataclasses import dataclass, field
from uuid import UUID


@dataclass
class HumanLoopDecision:
    action: str  # "approve" | "reject" | "edit"
    content: str | None = None


@dataclass
class HumanLoopPoint:
    """Configuration for a human-in-the-loop breakpoint."""

    trigger: str = "never"  # "always" | "on_low_score" | "on_first_run" | "never"
    timeout_hours: float = 24.0
    fallback: str = "pause"  # "auto_accept" | "auto_reject" | "pause"
    score_threshold: float = 0.7

    def should_pause(self, score: float = 1.0, is_first_run: bool = False) -> bool:
        """Determine if pipeline should pause at this point."""
        if self.trigger == "never":
            return False
        if self.trigger == "always":
            return True
        if self.trigger == "on_low_score":
            return score < self.score_threshold
        if self.trigger == "on_first_run":
            return is_first_run
        return False


@dataclass
class PendingLoop:
    node_name: str
    data: dict = field(default_factory=dict)
    decision: HumanLoopDecision | None = None


class HumanLoopManager:
    """Manages pending human-in-the-loop decisions."""

    def __init__(self):
        self._pending: dict[UUID, PendingLoop] = {}

    def create_pending(self, loop_id: UUID, node_name: str, data: dict | None = None) -> None:
        """Create a pending human loop request."""
        self._pending[loop_id] = PendingLoop(node_name=node_name, data=data or {})

    def is_pending(self, loop_id: UUID) -> bool:
        """Check if a loop is still pending."""
        loop = self._pending.get(loop_id)
        return loop is not None and loop.decision is None

    def submit_decision(self, loop_id: UUID, decision: HumanLoopDecision) -> None:
        """Submit a human decision for a pending loop."""
        loop = self._pending.get(loop_id)
        if loop is None:
            raise ValueError(f"Loop {loop_id} not found")
        loop.decision = decision

    def get_decision(self, loop_id: UUID) -> HumanLoopDecision | None:
        """Get the decision for a loop."""
        loop = self._pending.get(loop_id)
        if loop is None:
            return None
        return loop.decision
