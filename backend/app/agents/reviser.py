# backend/app/agents/reviser.py
"""Reviser Agent: Five-mode chapter revision.

Modes:
- polish: Light touch-up (grammar, flow, repetition)
- rewrite: Rewrite problematic sections keeping plot
- rework: Major structural rework
- spot-fix: Fix only listed issues
- anti-detect: Remove AI traces using De-AI engine data
"""

import json
from typing import Any

from app.agents.base import BaseAgent
from app.engines.de_ai import DeAIEngine
from app.providers.base import ChatMessage
from app.schemas.agent import AgentContext, ReviserOutput, ValidationIssue


class ReviserAgent(BaseAgent):
    name = "reviser"
    description = "Revises chapter content based on audit feedback"
    temperature = 0.5
    output_schema = ReviserOutput

    MODE_PROMPTS = {
        "polish": "Lightly polish the text: fix grammar, improve flow, remove repetition. Keep the original style intact.",
        "rewrite": "Rewrite problematic sections while maintaining plot continuity and character consistency.",
        "rework": "Significantly rework the chapter to address major structural issues. Maintain core plot points.",
        "spot-fix": "Fix only the specific issues listed below. Do not change anything else.",
        "anti-detect": "Rewrite to remove AI-like patterns while preserving meaning, style, and character voices.",
    }

    SYSTEM_PROMPT = """You are a professional novel editor.
Revise the given chapter text according to the specified mode.

Respond in valid JSON:
{
    "revised_content": "the revised full text",
    "changes_summary": "brief description of changes made",
    "word_count": 1234
}"""

    def __init__(self, provider, model: str = "gpt-4o"):
        super().__init__(provider, model)
        self.de_ai = DeAIEngine()

    async def build_messages(self, context: AgentContext) -> list[ChatMessage]:
        # Support both old format (pipeline_data.content) and new format (pipeline_data.writer.phase1_content)
        writer_data = context.pipeline_data.get("writer", {})
        content = writer_data.get("phase1_content", "") if writer_data else ""
        if not content:
            content = context.pipeline_data.get("content", "")

        # Support both old format (pipeline_data.audit_issues) and new format (pipeline_data.auditor.issues)
        auditor_data = context.pipeline_data.get("auditor", {})
        audit_issues = auditor_data.get("issues", []) if auditor_data else []
        if not audit_issues:
            audit_issues = context.pipeline_data.get("audit_issues", [])

        # Mode from params (new) or pipeline_data (old)
        mode = context.params.get("mode", "") or context.pipeline_data.get("mode", "polish")

        mode_instruction = self.MODE_PROMPTS.get(mode, self.MODE_PROMPTS["polish"])

        user_parts = [f"## Revision mode: {mode}\n{mode_instruction}\n"]

        # Include audit issues for all modes
        if audit_issues:
            user_parts.append("## Audit issues to address:")
            for issue in audit_issues:
                dim = issue.get("dimension", "unknown")
                msg = issue.get("message", "")
                sev = issue.get("severity", "warning")
                user_parts.append(f"- [{sev}] {dim}: {msg}")
            user_parts.append("")

        # Anti-detect mode: inject fatigue words and banned patterns
        if mode == "anti-detect":
            de_ai_text = self.de_ai.format_for_prompt(top_words=100, top_patterns=30)
            user_parts.append(de_ai_text)
            user_parts.append("")

            # Run detection and include specific traces found
            traces = self.de_ai.detect(content)
            if traces:
                user_parts.append(f"## AI traces detected in this text ({len(traces)} total):")
                # Group by type
                fatigue = [t for t in traces if t["type"] == "fatigue_word"]
                banned = [t for t in traces if t["type"] == "banned_pattern"]
                if fatigue:
                    unique_words = list(set(t["matched"] for t in fatigue))[:30]
                    user_parts.append(f"疲劳词: {'、'.join(unique_words)}")
                if banned:
                    unique_patterns = list(set(t.get("pattern_name", t["matched"]) for t in banned))[:10]
                    user_parts.append(f"模板句式: {'、'.join(unique_patterns)}")
                user_parts.append("")

        user_parts.append(f"## Original text:\n{content[:8000]}")

        return [
            ChatMessage(role="system", content=self.SYSTEM_PROMPT),
            ChatMessage(role="user", content="\n".join(user_parts)),
        ]

    async def _call_llm(
        self, messages: list[ChatMessage], context: AgentContext
    ) -> dict[str, Any]:
        response = await self.provider.chat(
            messages=messages, model=self.model, temperature=self.temperature,
        )
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {
                "revised_content": response.content,
                "changes_summary": "Raw response (JSON parse failed)",
                "word_count": len(response.content),
            }

    async def validate_output(self, result: Any) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if not isinstance(result, dict):
            issues.append(ValidationIssue(field="result", message="Expected dict", severity="error"))
            return issues
        if not result.get("revised_content"):
            issues.append(ValidationIssue(field="revised_content", message="Empty revised content", severity="error"))
        return issues
