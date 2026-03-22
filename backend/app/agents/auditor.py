"""Auditor Agent: basic quality audit framework."""
import json
from typing import Any
from app.agents.base import BaseAgent
from app.providers.base import ChatMessage
from app.schemas.agent import AgentContext, AuditorOutput


class AuditorAgent(BaseAgent):
    name = "auditor"
    description = "Audits chapter quality across multiple dimensions"
    temperature = 0.2
    output_schema = AuditorOutput

    SYSTEM_PROMPT = """You are a quality auditor for a novel writing system.
Evaluate the given chapter text across these dimensions:
- consistency: Character behavior, world rules, timeline
- narrative: Plot advancement, scene goals, tension
- character: Dialogue consistency, character development
- structure: Three-act structure, pacing
- style: Writing quality, repetition, AI traces

For each dimension, give a score from 0-10.

Respond in valid JSON:
{
    "scores": {"dimension_name": score},
    "pass_rate": 0.0-1.0,
    "has_blocking": true/false,
    "issues": [{"dimension": "...", "message": "...", "severity": "pass|warning|error|blocking"}],
    "recommendation": "pass" | "revise" | "rework"
}
"""

    async def build_messages(self, context: AgentContext) -> list[ChatMessage]:
        content = context.pipeline_data.get("content", "")
        mode = context.pipeline_data.get("mode", "full")
        return [ChatMessage(role="system", content=self.SYSTEM_PROMPT), ChatMessage(role="user", content=f"Audit mode: {mode}\n\nChapter content:\n{content}")]

    async def _call_llm(self, messages: list[ChatMessage], context: AgentContext) -> Any:
        resp = await self.provider.chat(messages=messages, model=self.model, temperature=self.temperature)
        return json.loads(resp.content)
