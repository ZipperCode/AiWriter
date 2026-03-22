"""Base class for all agents in the pipeline."""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, Type

from pydantic import BaseModel

from app.providers.base import BaseLLMProvider, ChatMessage
from app.schemas.agent import AgentContext, AgentResult, ValidationIssue


class BaseAgent(ABC):
    """Abstract base class for pipeline agents.

    Provides: LLM integration via provider, retry with exponential backoff,
    output validation, execution timing, and optional schema-based auto-validation.
    """

    name: str = ""
    description: str = ""
    system_prompt_template: str = ""
    input_schema: Type[BaseModel] | None = None
    output_schema: Type[BaseModel] | None = None
    temperature: float = 0.7
    max_retries: int = 3
    timeout_seconds: int = 120

    def __init__(self, provider: BaseLLMProvider, model: str = "gpt-4o"):
        self.provider = provider
        self.model = model

    async def execute(self, context: AgentContext) -> AgentResult:
        """Execute the agent with retry logic and optional timeout."""
        start = time.monotonic()
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                messages = await self.build_messages(context)
                raw_result = await asyncio.wait_for(
                    self._call_llm(messages, context),
                    timeout=self.timeout_seconds,
                )

                # Auto-validate with output_schema if set
                if self.output_schema and isinstance(raw_result, dict):
                    raw_result = self.output_schema(**raw_result).model_dump()

                # Custom validation
                issues = await self.validate_output(raw_result)
                blocking = [i for i in issues if i.severity == "error"]
                if blocking and attempt < self.max_retries:
                    raise ValueError(
                        f"Validation failed: {[i.message for i in blocking]}"
                    )

                elapsed = int((time.monotonic() - start) * 1000)
                data = self._to_dict(raw_result)
                return AgentResult(
                    agent_name=self.name,
                    success=True,
                    data=data,
                    duration_ms=elapsed,
                )
            except asyncio.TimeoutError:
                last_error = TimeoutError(
                    f"{self.name} timed out after {self.timeout_seconds}s"
                )
                if attempt < self.max_retries:
                    await self.on_retry(last_error, attempt)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    await self.on_retry(e, attempt)

        elapsed = int((time.monotonic() - start) * 1000)
        return AgentResult(
            agent_name=self.name,
            success=False,
            error=str(last_error),
            duration_ms=elapsed,
        )

    @abstractmethod
    async def build_messages(self, context: AgentContext) -> list[ChatMessage]:
        """Build the message list for the LLM call."""
        ...

    @abstractmethod
    async def _call_llm(
        self, messages: list[ChatMessage], context: AgentContext
    ) -> Any:
        """Make the actual LLM call and parse the response."""
        ...

    async def validate_output(self, result: Any) -> list[ValidationIssue]:
        """Validate agent output. Override for custom validation."""
        return []

    async def on_retry(self, error: Exception, attempt: int) -> None:
        """Called before retry. Default: exponential backoff."""
        wait = min(2**attempt, 30)
        await asyncio.sleep(wait)

    @staticmethod
    def _to_dict(result: Any) -> dict[str, Any]:
        """Convert result to dict for AgentResult.data."""
        if isinstance(result, dict):
            return result
        if isinstance(result, BaseModel):
            return result.model_dump()
        return {"raw": str(result)}
