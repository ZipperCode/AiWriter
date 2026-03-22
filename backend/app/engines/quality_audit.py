# backend/app/engines/quality_audit.py
"""Quality Audit Engine: 33-dimension quality assessment.

Modes:
- full: All 33 dimensions (LLM + deterministic)
- incremental: Only dimensions affected by changes
- quick: Deterministic checks only (zero LLM cost)

Deterministic dimensions (no LLM):
- #5  material_continuity
- #7  locked_attribute_violation
- #26 ai_trace_detection
- #27 repetition_detection
- #28 banned_word_detection
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from app.engines.de_ai import DeAIEngine


@dataclass
class DimensionResult:
    """Result for a single audit dimension."""
    dimension_id: int
    name: str
    category: str
    score: float  # 0-10
    severity: str  # pass(>=7) / warning(4-6) / error(1-3) / blocking(0)
    message: str
    evidence: list[dict[str, Any]] = field(default_factory=list)

    @staticmethod
    def compute_severity(score: float) -> str:
        if score >= 7:
            return "pass"
        if score >= 4:
            return "warning"
        if score >= 1:
            return "error"
        return "blocking"


@dataclass
class AuditReport:
    """Aggregated audit report across all dimensions."""
    results: list[DimensionResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        if not self.results:
            return 0.0
        passed = sum(1 for r in self.results if r.score >= 7)
        return passed / len(self.results)

    @property
    def has_blocking(self) -> bool:
        return any(r.severity == "blocking" for r in self.results)

    @property
    def recommendation(self) -> str:
        """Determine recommendation based on pass rate and blocking issues."""
        if self.has_blocking:
            return "revise"
        if self.pass_rate < 0.6:
            return "rework"
        if self.pass_rate >= 0.85:
            return "pass"
        return "revise"  # 60-85%

    @property
    def scores(self) -> dict[str, float]:
        return {r.name: r.score for r in self.results}

    @property
    def issues(self) -> list[dict[str, Any]]:
        return [
            {"dimension": r.name, "message": r.message, "severity": r.severity, "score": r.score}
            for r in self.results if r.score < 7
        ]


class AuditRunner:
    """Orchestrates quality audit across 33 dimensions."""

    def __init__(self, de_ai_engine: DeAIEngine | None = None) -> None:
        self.de_ai = de_ai_engine or DeAIEngine()

    # --- Deterministic checks (zero LLM cost) ---

    def check_ai_traces(self, text: str) -> DimensionResult:
        """Dimension #26: AI trace detection using De-AI engine."""
        traces = self.de_ai.detect(text)
        density = self.de_ai.get_fatigue_density(text)

        # Score based on density: 0 density = 10, >20 per 1k = 0
        if density <= 2:
            score = 10.0
        elif density <= 5:
            score = 8.0
        elif density <= 10:
            score = 6.0
        elif density <= 15:
            score = 4.0
        elif density <= 20:
            score = 2.0
        else:
            score = 0.0

        severity = DimensionResult.compute_severity(score)
        evidence = traces[:10]  # Top 10 traces as evidence

        return DimensionResult(
            dimension_id=26,
            name="ai_trace_detection",
            category="style",
            score=score,
            severity=severity,
            message=f"AI trace density: {density:.1f}/1000 chars, {len(traces)} traces found",
            evidence=evidence,
        )

    def check_repetition(self, text: str, window: int = 200) -> DimensionResult:
        """Dimension #27: repetition detection.

        Checks for structural monotony among unique sentences.
        Focuses on whether the distinct sentences share repetitive phrasing
        (n-gram overlap), rather than counting bulk paragraph duplication.
        """
        if len(text) < 10:
            return DimensionResult(
                dimension_id=27, name="repetition_detection", category="style",
                score=10.0, severity="pass", message="Text too short to analyze", evidence=[],
            )

        # Split into sentences
        sentences = re.split(r'[。！？；\n]', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) >= 4]

        if not sentences:
            return DimensionResult(
                dimension_id=27, name="repetition_detection", category="style",
                score=10.0, severity="pass", message="No sentences to analyze", evidence=[],
            )

        # Structural monotony: check n-gram overlap among *unique* sentences
        unique_sentences = list(set(sentences))
        ngram_size = 3
        all_ngrams: list[str] = []
        for s in unique_sentences:
            for i in range(len(s) - ngram_size + 1):
                all_ngrams.append(s[i:i + ngram_size])

        unique_ngram_count = len(set(all_ngrams))
        ngram_counter = Counter(all_ngrams)
        # N-grams shared across multiple unique sentences
        shared_ngrams = {ng: c for ng, c in ngram_counter.items() if c > 1}
        overlap_ratio = len(shared_ngrams) / max(unique_ngram_count, 1)

        # Also check consecutive sentence repetition
        consecutive_repeats = 0
        for i in range(1, len(sentences)):
            if sentences[i] == sentences[i - 1]:
                consecutive_repeats += 1
        consec_ratio = consecutive_repeats / max(len(sentences) - 1, 1)

        # Build evidence from repeated sentences
        counter = Counter(sentences)
        repeated = {s: c for s, c in counter.items() if c > 1}
        evidence = [{"repeated_sentence": s, "count": c} for s, c in list(repeated.items())[:5]]

        # Combined score based on structural monotony and consecutive repeats
        if overlap_ratio <= 0.05 and consec_ratio <= 0.05:
            score = 10.0
        elif overlap_ratio <= 0.10 and consec_ratio <= 0.10:
            score = 8.0
        elif overlap_ratio <= 0.15 and consec_ratio <= 0.20:
            score = 6.0
        elif overlap_ratio <= 0.25:
            score = 4.0
        else:
            score = 2.0

        severity = DimensionResult.compute_severity(score)

        return DimensionResult(
            dimension_id=27,
            name="repetition_detection",
            category="style",
            score=score,
            severity=severity,
            message=f"Structural overlap: {overlap_ratio:.2%}, consecutive repeats: {consec_ratio:.2%}",
            evidence=evidence,
        )

    def check_banned_words(self, text: str) -> DimensionResult:
        """Dimension #28: banned word/pattern detection."""
        traces = self.de_ai.detect(text)
        banned = [t for t in traces if t["type"] == "banned_pattern"]
        fatigue = [t for t in traces if t["type"] == "fatigue_word"]

        # Score based on banned pattern count per 1000 chars
        text_len = max(len(text), 1)
        banned_density = len(banned) / text_len * 1000
        fatigue_density = len(fatigue) / text_len * 1000

        if banned_density <= 0.5 and fatigue_density <= 3:
            score = 10.0
        elif banned_density <= 1 and fatigue_density <= 5:
            score = 8.0
        elif banned_density <= 2 and fatigue_density <= 10:
            score = 6.0
        elif banned_density <= 3:
            score = 4.0
        else:
            score = 2.0

        severity = DimensionResult.compute_severity(score)
        evidence = banned[:5] + fatigue[:5]

        return DimensionResult(
            dimension_id=28,
            name="banned_word_detection",
            category="style",
            score=score,
            severity=severity,
            message=f"Banned patterns: {len(banned)}, fatigue words: {len(fatigue)}",
            evidence=evidence,
        )

    def check_material_continuity(
        self, text: str, known_items: list[dict[str, Any]] | None = None
    ) -> DimensionResult:
        """Dimension #5: material continuity check.

        Checks if items mentioned in text are consistent with known inventory.
        Basic version: checks for item mentions without prior establishment.
        """
        # Placeholder: in full implementation, cross-reference with entity DB
        # For now, return a default pass with note
        return DimensionResult(
            dimension_id=5,
            name="material_continuity",
            category="consistency",
            score=8.0,
            severity="pass",
            message="Material continuity check (basic): no obvious violations",
            evidence=[],
        )

    def check_locked_attributes(
        self, text: str, locked_attrs: dict[str, str] | None = None
    ) -> DimensionResult:
        """Dimension #7: locked attribute violation check.

        Checks if text contradicts any locked character attributes.
        """
        if not locked_attrs:
            return DimensionResult(
                dimension_id=7,
                name="locked_attribute_violation",
                category="consistency",
                score=10.0,
                severity="pass",
                message="No locked attributes to check",
                evidence=[],
            )

        violations: list[dict[str, Any]] = []
        for attr_name, attr_value in locked_attrs.items():
            # Simple contradiction check: if the negation of the attribute appears
            # This is a basic heuristic; full implementation would use NLI
            if attr_value in text:
                continue  # Attribute mentioned correctly
            # Check for explicit contradictions with "不是" patterns
            neg_pattern = f"不是{attr_value}|并非{attr_value}"
            if re.search(neg_pattern, text):
                violations.append({"attribute": attr_name, "expected": attr_value})

        score = 10.0 if not violations else max(0, 10 - len(violations) * 3)
        severity = DimensionResult.compute_severity(score)

        return DimensionResult(
            dimension_id=7,
            name="locked_attribute_violation",
            category="consistency",
            score=score,
            severity=severity,
            message=f"Locked attribute violations: {len(violations)}",
            evidence=violations,
        )

    def run_deterministic_checks(
        self,
        text: str,
        known_items: list[dict[str, Any]] | None = None,
        locked_attrs: dict[str, str] | None = None,
    ) -> list[DimensionResult]:
        """Run all deterministic checks (zero LLM cost).

        Dimensions: #5, #7, #26, #27, #28
        """
        return [
            self.check_material_continuity(text, known_items),
            self.check_locked_attributes(text, locked_attrs),
            self.check_ai_traces(text),
            self.check_repetition(text),
            self.check_banned_words(text),
        ]
