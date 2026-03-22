"""Settler Agent: extracts facts and updates truth files after writing."""
import json
from typing import Any
from app.agents.base import BaseAgent
from app.providers.base import ChatMessage
from app.schemas.agent import AgentContext, SettlerOutput


class SettlerAgent(BaseAgent):
    name = "settler"
    description = "Extracts facts from written content and updates truth files"
    temperature = 0.2
    output_schema = SettlerOutput

    SYSTEM_PROMPT = """You are a fact extraction agent for a novel writing system.
Given a chapter's text and initial settlement data, extract entities and compute truth file diffs.

Respond in valid JSON:
{
    "extracted_entities": [{"name": "...", "type": "character|location|faction|item|concept", "confidence": 0.0-1.0}],
    "truth_file_updates": {"current_state": {...}, "chapter_summaries": {...}}
}
Only include truth file keys that actually need updates.
"""

    async def build_messages(self, context: AgentContext) -> list[ChatMessage]:
        content = context.pipeline_data.get("content", "")
        settlement = context.pipeline_data.get("settlement", {})
        user_msg = f"Chapter content:\n{content}\n\n"
        if settlement:
            user_msg += f"Writer settlement data:\n{json.dumps(settlement, ensure_ascii=False, default=str)}\n\n"
        user_msg += "Extract all facts and compute truth file diffs."
        return [ChatMessage(role="system", content=self.SYSTEM_PROMPT), ChatMessage(role="user", content=user_msg)]

    async def _call_llm(self, messages: list[ChatMessage], context: AgentContext) -> Any:
        resp = await self.provider.chat(messages=messages, model=self.model, temperature=self.temperature)
        return json.loads(resp.content)
