"""Writer Agent: Phase1 (creative writing) + Phase2 (state settlement extraction)."""
import json
from typing import Any
from app.agents.base import BaseAgent
from app.providers.base import ChatMessage
from app.schemas.agent import AgentContext, WriterOutput


class WriterAgent(BaseAgent):
    name = "writer"
    description = "Writes novel chapters (Phase1: creative, Phase2: settlement)"
    temperature = 0.7
    output_schema = WriterOutput

    DEFAULT_SYSTEM = """You are a professional novel writer. Write vivid, engaging prose.
Rules:
- Show, don't tell
- Each scene must advance at least one conflict
- Dialogue must reflect character personality
- Include at least two sensory details per scene
- Write directly in prose, no metadata or annotations
"""

    SETTLEMENT_SYSTEM = """You are a fact extractor. Given a chapter text, extract:
1. New entities mentioned
2. State changes
3. A brief summary (1-2 sentences)

Respond in valid JSON:
{"new_entities": [{"name": "...", "type": "..."}], "state_changes": {"key": "value"}, "summary": "..."}
"""

    async def build_messages(self, context: AgentContext) -> list[ChatMessage]:
        ctx_data = context.pipeline_data.get("context", {})
        system = ctx_data.get("system_prompt", self.DEFAULT_SYSTEM)
        user = ctx_data.get("user_prompt", "Please write this chapter.")
        target_words = context.params.get("target_words", 3000)
        user += f"\n\nTarget word count: {target_words} characters."
        return [ChatMessage(role="system", content=system), ChatMessage(role="user", content=user)]

    async def _call_llm(self, messages: list[ChatMessage], context: AgentContext) -> Any:
        resp1 = await self.provider.chat(messages=messages, model=self.model, temperature=0.7)
        phase1_content = resp1.content
        phase2_messages = [
            ChatMessage(role="system", content=self.SETTLEMENT_SYSTEM),
            ChatMessage(role="user", content=f"Extract facts from this chapter:\n\n{phase1_content}"),
        ]
        resp2 = await self.provider.chat(messages=phase2_messages, model=self.model, temperature=0.3)
        try:
            phase2_data = json.loads(resp2.content)
        except json.JSONDecodeError:
            phase2_data = {"summary": resp2.content}
        return {"phase1_content": phase1_content, "phase2_settlement": phase2_data, "word_count": len(phase1_content)}
