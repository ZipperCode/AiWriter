"""Audit Records + Dimensions API."""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, verify_token
from app.engines.quality_audit import AuditRunner
from app.engines.rules_engine import AUDIT_DIMENSIONS
from app.models.audit_record import AuditRecord
from app.schemas.audit import DimensionListResponse

router = APIRouter(prefix="/api", tags=["audit"], dependencies=[Depends(verify_token)])


class QuickAuditRequest(BaseModel):
    text: str


@router.get("/audit/dimensions", response_model=DimensionListResponse)
async def list_dimensions():
    """List all 33 audit dimensions."""
    return DimensionListResponse(
        dimensions=AUDIT_DIMENSIONS,
        total=len(AUDIT_DIMENSIONS),
        active=len(AUDIT_DIMENSIONS),
    )


@router.get("/chapters/{chapter_id}/audit-records")
async def list_audit_records(
    chapter_id: UUID, db: AsyncSession = Depends(get_db),
):
    """List audit records for a chapter."""
    stmt = (
        select(AuditRecord)
        .where(AuditRecord.chapter_id == chapter_id)
        .order_by(AuditRecord.dimension)
    )
    result = await db.execute(stmt)
    records = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "chapter_id": str(r.chapter_id),
            "draft_id": str(r.draft_id),
            "dimension": r.dimension,
            "category": r.category,
            "score": r.score,
            "severity": r.severity,
            "message": r.message,
            "evidence": r.evidence,
        }
        for r in records
    ]


@router.post("/audit/quick")
async def quick_audit(body: QuickAuditRequest):
    """Run quick (deterministic-only) audit on text. Zero LLM cost."""
    runner = AuditRunner()
    results = runner.run_deterministic_checks(body.text)
    scores = {r.name: r.score for r in results}
    pass_rate = sum(1 for r in results if r.score >= 7) / max(len(results), 1)
    has_blocking = any(r.severity == "blocking" for r in results)
    issues = [
        {"dimension": r.name, "message": r.message, "severity": r.severity}
        for r in results if r.score < 7
    ]
    return {
        "scores": scores,
        "pass_rate": pass_rate,
        "has_blocking": has_blocking,
        "issues": issues,
    }
