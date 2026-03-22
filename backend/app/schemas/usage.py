"""Schemas for usage tracking endpoints."""

from pydantic import BaseModel, Field


class UsageSummary(BaseModel):
    """Summary of total usage across all records."""

    total_input_tokens: int = Field(..., description="Total input tokens consumed")
    total_output_tokens: int = Field(..., description="Total output tokens produced")
    total_cost: float = Field(..., description="Total cost in dollars")
    total_calls: int = Field(..., description="Total number of usage records")


class UsageByModel(BaseModel):
    """Usage grouped by model."""

    model: str = Field(..., description="Model name (e.g., gpt-4)")
    total_input_tokens: int = Field(..., description="Total input tokens for this model")
    total_output_tokens: int = Field(..., description="Total output tokens for this model")
    total_cost: float = Field(..., description="Total cost for this model")
    call_count: int = Field(..., description="Number of calls to this model")


class UsageByAgent(BaseModel):
    """Usage grouped by agent."""

    agent_name: str = Field(..., description="Agent name")
    total_input_tokens: int = Field(..., description="Total input tokens for this agent")
    total_output_tokens: int = Field(..., description="Total output tokens for this agent")
    total_cost: float = Field(..., description="Total cost for this agent")
    call_count: int = Field(..., description="Number of calls from this agent")
