"""Architect Agent: structure planning (plot blueprint, volume outline, chapters, scene cards)."""

import json
from typing import Any
from app.agents.base import BaseAgent
from app.providers.base import ChatMessage
from app.schemas.agent import AgentContext, ArchitectOutput


# --- Golden Three Chapters constraints ---
GOLDEN_THREE_CHAPTERS: dict[int, str] = {
    1: "【黄金三章·第1章约束】第1章必须立即抛出核心冲突，禁止大段背景灌输。场景卡必须包含核心冲突标记。快速抓住读者注意力。",
    2: "【黄金三章·第2章约束】第2章必须展示金手指/核心能力，让读者看到爽点预期。场景卡必须包含金手指展示标记。建立阅读期待。",
    3: "【黄金三章·第3章约束】第3章必须明确短期目标，给读者追读理由。场景卡必须包含短期目标明确标记。留住读者。",
}


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

        messages = [
            ChatMessage(role="system", content=self.SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_content),
        ]

        # Golden Three Chapters: inject constraint for chapters 1-3
        chapter_sort_order = context.params.get("chapter_sort_order")
        golden_constraint = GOLDEN_THREE_CHAPTERS.get(chapter_sort_order)  # type: ignore[arg-type]
        if golden_constraint:
            messages.append(ChatMessage(role="system", content=golden_constraint))

        return messages

    async def _call_llm(self, messages: list[ChatMessage], context: AgentContext) -> Any:
        resp = await self.provider.chat(messages=messages, model=self.model, temperature=self.temperature)
        parsed = json.loads(resp.content)
        return parsed
