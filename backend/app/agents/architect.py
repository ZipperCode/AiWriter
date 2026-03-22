"""Architect Agent: structure planning (plot blueprint, volume outline, chapters, scene cards)."""

import json
from typing import Any
from app.agents.base import BaseAgent
from app.providers.base import ChatMessage
from app.schemas.agent import AgentContext, ArchitectOutput


class ArchitectAgent(BaseAgent):
    name = "architect"
    description = "Plans story structure: outlines, chapters, and scene cards"
    temperature = 0.4
    output_schema = ArchitectOutput

    SYSTEM_PROMPT = """You are a story architect for a novel writing system.
Your job is to create structured outlines and plans for novels.

You must respond with valid JSON matching this schema:
{
    "stage": "<the planning stage>",
    "content": { <structured content varies by stage> }
}

Planning stages:
- "plot_blueprint": Overall story arc with major turning points
- "volume_outline": Volume-level structure with objectives and climax hints
- "chapter_plan": List of chapters with titles, summaries, and sort orders
- "scene_cards": Detailed scene breakdowns with location, goal, conflict, outcome

Guidelines:
- Each chapter should have clear goals and conflicts
- Scene cards must include at least: location, goal, and conflict
- Follow the genre conventions provided in context
"""

    async def build_messages(self, context: AgentContext) -> list[ChatMessage]:
        stage = context.params.get("stage", "chapter_plan")
        user_content = f"Planning stage: {stage}\n\n"
        if context.pipeline_data:
            user_content += f"Context:\n{json.dumps(context.pipeline_data, ensure_ascii=False, default=str)}\n\n"
        if context.volume_id:
            user_content += f"Volume ID: {context.volume_id}\n"
        if context.chapter_id:
            user_content += f"Chapter ID: {context.chapter_id}\n"
        user_content += f"\nPlease create the {stage} structure."
        return [
            ChatMessage(role="system", content=self.SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_content),
        ]

    async def _call_llm(self, messages: list[ChatMessage], context: AgentContext) -> Any:
        resp = await self.provider.chat(messages=messages, model=self.model, temperature=self.temperature)
        parsed = json.loads(resp.content)
        return parsed
