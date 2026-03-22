"""Usage tracking service for recording LLM token/cost usage."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage_record import UsageRecord


class UsageService:
    """Service for recording and querying LLM usage data."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        agent_name: str | None = None,
        job_run_id: UUID | None = None,
        provider_config_id: UUID | None = None,
    ) -> UsageRecord:
        """Record a new usage entry.

        Args:
            model: Model name (e.g., 'gpt-4', 'gpt-3.5-turbo')
            input_tokens: Number of input tokens consumed
            output_tokens: Number of output tokens produced
            cost: Cost in dollars
            agent_name: Optional agent name that performed the operation
            job_run_id: Optional job run ID this usage belongs to
            provider_config_id: Optional provider configuration ID

        Returns:
            Created UsageRecord instance
        """
        record = UsageRecord(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            agent_name=agent_name,
            job_run_id=job_run_id,
            provider_config_id=provider_config_id,
        )
        self.db.add(record)
        await self.db.flush()
        return record

    async def get_summary(self) -> dict:
        """Get aggregate usage summary across all records.

        Returns:
            Dict with keys:
            - total_input_tokens: Sum of all input tokens
            - total_output_tokens: Sum of all output tokens
            - total_cost: Sum of all costs
            - total_calls: Number of usage records
        """
        # Count total records
        count_stmt = select(func.count(UsageRecord.id))
        count_result = await self.db.execute(count_stmt)
        total_calls = count_result.scalar() or 0

        # Sum tokens and cost
        sum_stmt = select(
            func.coalesce(func.sum(UsageRecord.input_tokens), 0).label("total_input"),
            func.coalesce(func.sum(UsageRecord.output_tokens), 0).label("total_output"),
            func.coalesce(func.sum(UsageRecord.cost), 0.0).label("total_cost"),
        )
        sum_result = await self.db.execute(sum_stmt)
        row = sum_result.one()

        return {
            "total_input_tokens": int(row.total_input),
            "total_output_tokens": int(row.total_output),
            "total_cost": float(row.total_cost),
            "total_calls": total_calls,
        }

    async def get_by_model(self) -> list[dict]:
        """Get usage grouped by model.

        Returns:
            List of dicts with keys:
            - model: Model name
            - total_input_tokens: Sum of input tokens for this model
            - total_output_tokens: Sum of output tokens for this model
            - total_cost: Sum of costs for this model
            - call_count: Number of calls for this model
        """
        stmt = select(
            UsageRecord.model,
            func.sum(UsageRecord.input_tokens).label("total_input"),
            func.sum(UsageRecord.output_tokens).label("total_output"),
            func.sum(UsageRecord.cost).label("total_cost"),
            func.count(UsageRecord.id).label("call_count"),
        ).group_by(UsageRecord.model)

        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            {
                "model": row.model,
                "total_input_tokens": row.total_input or 0,
                "total_output_tokens": row.total_output or 0,
                "total_cost": float(row.total_cost) if row.total_cost else 0.0,
                "call_count": row.call_count or 0,
            }
            for row in rows
        ]

    async def get_by_agent(self) -> list[dict]:
        """Get usage grouped by agent_name (excluding None values).

        Returns:
            List of dicts with keys:
            - agent_name: Agent name
            - total_input_tokens: Sum of input tokens for this agent
            - total_output_tokens: Sum of output tokens for this agent
            - total_cost: Sum of costs for this agent
            - call_count: Number of calls for this agent
        """
        stmt = select(
            UsageRecord.agent_name,
            func.sum(UsageRecord.input_tokens).label("total_input"),
            func.sum(UsageRecord.output_tokens).label("total_output"),
            func.sum(UsageRecord.cost).label("total_cost"),
            func.count(UsageRecord.id).label("call_count"),
        ).where(UsageRecord.agent_name.isnot(None)).group_by(UsageRecord.agent_name)

        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            {
                "agent_name": row.agent_name,
                "total_input_tokens": row.total_input or 0,
                "total_output_tokens": row.total_output or 0,
                "total_cost": float(row.total_cost) if row.total_cost else 0.0,
                "call_count": row.call_count or 0,
            }
            for row in rows
        ]
