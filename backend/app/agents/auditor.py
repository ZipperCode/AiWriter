# backend/app/agents/auditor.py
"""Auditor Agent: 33-dimension quality audit.

Modes:
- full: All 33 dimensions (deterministic + LLM)
- incremental: Only affected dimensions
- quick: Deterministic only (zero LLM cost)

Deterministic dimensions handled by AuditRunner: #5, #7, #26, #27, #28
LLM-based dimensions: all others (28 dimensions)
"""

import json
from typing import Any

from app.agents.base import BaseAgent
from app.engines.de_ai import DeAIEngine
from app.engines.quality_audit import AuditRunner, AuditReport, DimensionResult
from app.engines.rules_engine import AUDIT_DIMENSIONS
from app.providers.base import ChatMessage
from app.schemas.agent import AgentContext, AuditorOutput, ValidationIssue


class AuditorAgent(BaseAgent):
    name = "auditor"
    description = "33-dimension quality audit for novel chapters"
    temperature = 0.2
    output_schema = AuditorOutput

    SYSTEM_PROMPT = """You are a quality auditor for a novel writing system.
You will be given a chapter text and must evaluate it on specific quality dimensions.

For each dimension, provide:
- score (0-10): 0=catastrophic, 1-3=error, 4-6=warning, 7-10=pass
- message: brief explanation

Respond in valid JSON with dimension IDs as keys:
{
    "1": {"score": 8.0, "message": "Character behavior is consistent"},
    "2": {"score": 7.0, "message": "Character memory is maintained"},
    ...
}

Only evaluate the dimensions listed below. Be strict but fair."""

    def __init__(self, provider, model: str = "gpt-4o"):
        super().__init__(provider, model)
        self.de_ai = DeAIEngine()
        self.audit_runner = AuditRunner(de_ai_engine=self.de_ai)

    def _extract_content(self, context: AgentContext) -> str:
        """Extract chapter content from context, supporting both old and new formats."""
        # New format: pipeline_data.writer.phase1_content
        writer_data = context.pipeline_data.get("writer", {})
        if isinstance(writer_data, dict) and writer_data.get("phase1_content"):
            return writer_data["phase1_content"]
        # Old format: pipeline_data.content
        return context.pipeline_data.get("content", "")

    def _extract_mode(self, context: AgentContext) -> str:
        """Extract audit mode, supporting both old and new formats."""
        # New format: params.mode
        mode = context.params.get("mode", "")
        if mode:
            return mode
        # Old format: pipeline_data.mode
        return context.pipeline_data.get("mode", "full")

    async def build_messages(self, context: AgentContext) -> list[ChatMessage]:
        content = self._extract_content(context)
        mode = self._extract_mode(context)

        if mode == "quick":
            return []  # No LLM needed for quick mode

        # Build dimension list for LLM (exclude deterministic)
        llm_dims = [d for d in AUDIT_DIMENSIONS if not d["is_deterministic"]]
        dim_text = "\n".join(
            f"- ID {d['id']}: {d['zh_name']} ({d['category']}) \u2014 {d['description']}"
            for d in llm_dims
        )

        return [
            ChatMessage(role="system", content=self.SYSTEM_PROMPT),
            ChatMessage(role="user", content=f"""## Dimensions to evaluate:
{dim_text}

## Chapter text:
{content[:8000]}"""),
        ]

    async def _call_llm(
        self, messages: list[ChatMessage], context: AgentContext
    ) -> dict[str, Any]:
        content = self._extract_content(context)
        mode = self._extract_mode(context)

        # Run deterministic checks always
        det_results = self.audit_runner.run_deterministic_checks(content)

        if mode == "quick":
            # Quick mode: deterministic only
            report = AuditReport(results=det_results)
            return {
                "scores": report.scores,
                "pass_rate": report.pass_rate,
                "has_blocking": report.has_blocking,
                "issues": report.issues,
                "recommendation": report.recommendation,
            }

        # Full/incremental mode: also call LLM for non-deterministic dimensions
        response = await self.provider.chat(
            messages=messages, model=self.model, temperature=self.temperature,
        )

        # Parse LLM response
        try:
            llm_scores = json.loads(response.content)
        except json.JSONDecodeError:
            llm_scores = {}

        # Convert LLM scores to DimensionResult
        llm_results: list[DimensionResult] = []
        for dim in AUDIT_DIMENSIONS:
            if dim["is_deterministic"]:
                continue
            dim_data = llm_scores.get(str(dim["id"]), {})
            score = float(dim_data.get("score", 5.0))
            message = dim_data.get("message", "No evaluation")
            llm_results.append(DimensionResult(
                dimension_id=dim["id"],
                name=dim["name"],
                category=dim["category"],
                score=score,
                severity=DimensionResult.compute_severity(score),
                message=message,
            ))

        # Combine results
        all_results = det_results + llm_results
        all_results.sort(key=lambda r: r.dimension_id)
        report = AuditReport(results=all_results)

        return {
            "scores": report.scores,
            "pass_rate": report.pass_rate,
            "has_blocking": report.has_blocking,
            "issues": report.issues,
            "recommendation": report.recommendation,
        }

    async def validate_output(self, result: Any) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if not isinstance(result, dict):
            issues.append(ValidationIssue(field="result", message="Expected dict", severity="error"))
            return issues
        if "recommendation" not in result:
            issues.append(ValidationIssue(field="recommendation", message="Missing recommendation", severity="error"))
        return issues
