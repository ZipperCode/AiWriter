"""Context Agent: non-LLM agent that assembles writing context from the database."""
import time
from typing import Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.engines.context_filter import ContextFilter
from app.providers.base import BaseLLMProvider, ChatMessage
from app.schemas.agent import AgentContext, AgentResult


class ContextAgent:
    """Non-LLM agent. Accepts provider/model for registry compatibility but ignores them."""
    name = "context"
    description = "Assembles writing context from DB (no LLM)"

    def __init__(self, provider: BaseLLMProvider | None = None, model: str = ""):
        self._db: AsyncSession | None = None

    def set_db(self, db: AsyncSession) -> "ContextAgent":
        self._db = db
        return self

    async def execute(self, context: AgentContext) -> AgentResult:
        start = time.monotonic()
        try:
            if self._db is None:
                raise RuntimeError("ContextAgent requires db session (call set_db())")
            if context.chapter_id is None:
                raise ValueError("chapter_id is required for ContextAgent")
            pov_id_str = context.params.get("pov_character_id")
            pov_id = UUID(pov_id_str) if pov_id_str else None
            cf = ContextFilter(self._db)
            assembled = await cf.assemble_context(context.chapter_id, pov_id)
            elapsed = int((time.monotonic() - start) * 1000)
            return AgentResult(agent_name=self.name, success=True, data=assembled, duration_ms=elapsed)
        except Exception as e:
            elapsed = int((time.monotonic() - start) * 1000)
            return AgentResult(agent_name=self.name, success=False, error=str(e), duration_ms=elapsed)
