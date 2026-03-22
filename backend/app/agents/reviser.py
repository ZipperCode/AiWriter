"""Reviser Agent: basic revision framework."""
import json
from typing import Any
from app.agents.base import BaseAgent
from app.providers.base import ChatMessage
from app.schemas.agent import AgentContext, ReviserOutput


class ReviserAgent(BaseAgent):
    name = "reviser"
    description = "Revises chapter content based on audit feedback"
    temperature = 0.5
    output_schema = ReviserOutput

    MODE_PROMPTS = {
        "polish": "Lightly polish the text: fix grammar, improve flow, remove repetition.",
        "rewrite": "Rewrite problematic sections while maintaining plot continuity.",
        "rework": "Significantly rework the chapter to address major structural issues.",
        "spot-fix": "Fix only the specific issues listed below.",
        "anti-detect": "Rewrite to remove AI-like patterns while preserving meaning and style.",
    }

    SYSTEM_PROMPT = """You are a professional novel editor.
Your job is to revise chapter content based on audit feedback.
Output ONLY the revised chapter text. No explanations, no metadata.
"""

    async def build_messages(self, context: AgentContext) -> list[ChatMessage]:
        content = context.pipeline_data.get("content", "")
        mode = context.pipeline_data.get("mode", "polish")
        issues = context.pipeline_data.get("audit_issues", [])
        mode_instruction = self.MODE_PROMPTS.get(mode, self.MODE_PROMPTS["polish"])
        user_parts = [f"Revision mode: {mode}", f"Instruction: {mode_instruction}"]
        if issues:
            user_parts.append(f"Issues to fix:\n{json.dumps(issues, ensure_ascii=False, default=str)}")
        user_parts.append(f"\nOriginal text:\n{content}")
        return [ChatMessage(role="system", content=self.SYSTEM_PROMPT), ChatMessage(role="user", content="\n\n".join(user_parts))]

    async def _call_llm(self, messages: list[ChatMessage], context: AgentContext) -> Any:
        resp = await self.provider.chat(messages=messages, model=self.model, temperature=self.temperature)
        mode = context.pipeline_data.get("mode", "polish")
        return {"revised_content": resp.content, "changes_summary": f"Revised in {mode} mode", "word_count": len(resp.content)}
