"""API endpoints for usage tracking."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, verify_token
from app.schemas.usage import UsageByAgent, UsageByModel, UsageSummary
from app.services.usage_service import UsageService

router = APIRouter(
    prefix="/api/usage",
    tags=["usage"],
    dependencies=[Depends(verify_token)],
)


@router.get("/summary", response_model=UsageSummary)
async def get_usage_summary(db: AsyncSession = Depends(get_db)):
    """Get aggregate usage summary across all records."""
    svc = UsageService(db)
    summary = await svc.get_summary()
    return UsageSummary(**summary)


@router.get("/by-model", response_model=list[UsageByModel])
async def get_usage_by_model(db: AsyncSession = Depends(get_db)):
    """Get usage grouped by model."""
    svc = UsageService(db)
    data = await svc.get_by_model()
    return [UsageByModel(**item) for item in data]


@router.get("/by-agent", response_model=list[UsageByAgent])
async def get_usage_by_agent(db: AsyncSession = Depends(get_db)):
    """Get usage grouped by agent."""
    svc = UsageService(db)
    data = await svc.get_by_agent()
    return [UsageByAgent(**item) for item in data]
