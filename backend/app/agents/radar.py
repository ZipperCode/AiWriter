"""Radar Agent: analyzes project state and determines next pipeline action."""

import json
from typing import Any

from app.agents.base import BaseAgent
from app.providers.base import ChatMessage
from app.schemas.agent import AgentContext, RadarOutput, ValidationIssue


class RadarAgent(BaseAgent):
    name = "radar"
    description = "Analyzes project state and determines the next action"
    temperature = 0.3
    output_schema = RadarOutput

    SYSTEM_PROMPT = """You are a project analysis agent for a novel writing system.
Your job is to analyze the current state of a writing project and determine what action should be taken next.

You must respond with valid JSON matching this schema:
{
    "next_action": "write_chapter" | "plan_volume" | "plan_chapters" | "done",
    "target_chapter_id": "<uuid or null>",
    "target_volume_id": "<uuid or null>",
    "reasoning": "<brief explanation>"
}

Rules:
- If there are planned chapters ready to write, return "write_chapter" with the chapter ID.
- If a volume needs chapter planning, return "plan_chapters" with the volume ID.
- If the project needs a new volume outline, return "plan_volume".
- If all chapters are finalized, return "done".
"""

    async def build_messages(self, context: AgentContext) -> list[ChatMessage]:
        user_content = "Analyze the current project state and determine the next action.\n\n"
        if context.pipeline_data:
            user_content += (
                f"Project data:\n"
                f"{json.dumps(context.pipeline_data, ensure_ascii=False, default=str)}"
            )
        else:
            user_content += f"Project ID: {context.project_id}"
        return [
            ChatMessage(role="system", content=self.SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_content),
        ]

    async def _call_llm(self, messages: list[ChatMessage], context: AgentContext) -> Any:
        resp = await self.provider.chat(
            messages=messages, model=self.model, temperature=self.temperature
        )
        parsed = json.loads(resp.content)
        return parsed

    async def validate_output(self, result: Any) -> list[ValidationIssue]:
        issues = []
        if isinstance(result, dict):
            action = result.get("next_action", "")
            valid_actions = {"write_chapter", "plan_volume", "plan_chapters", "done"}
            if action not in valid_actions:
                issues.append(
                    ValidationIssue(
                        field="next_action",
                        message=f"Invalid action: {action}",
                        severity="error",
                    )
                )
        return issues
