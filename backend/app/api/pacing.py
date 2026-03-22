"""Pacing Analysis API."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, verify_token
from app.engines.pacing_control import PacingController

router = APIRouter(prefix="/api", tags=["pacing"], dependencies=[Depends(verify_token)])


@router.get("/projects/{project_id}/pacing")
async def get_pacing_analysis(
    project_id: UUID, db: AsyncSession = Depends(get_db),
):
    """Get overall pacing analysis for a project."""
    ctrl = PacingController(db)
    analysis = await ctrl.analyze_pacing(project_id)
    return {
        "chapter_pacing": [
            {
                "chapter_id": str(cp.chapter_id),
                "sort_order": cp.sort_order,
                "quest_ratio": cp.quest_ratio,
                "fire_ratio": cp.fire_ratio,
                "constellation_ratio": cp.constellation_ratio,
                "highlight_count": cp.highlight_count,
                "highlight_types": cp.highlight_types,
                "tension_level": cp.tension_level,
                "strand_tags": cp.strand_tags,
            }
            for cp in analysis.chapter_pacing
        ],
        "avg_quest_ratio": analysis.avg_quest_ratio,
        "avg_fire_ratio": analysis.avg_fire_ratio,
        "avg_constellation_ratio": analysis.avg_constellation_ratio,
        "total_highlights": analysis.total_highlights,
        "avg_tension": analysis.avg_tension,
    }


@router.get("/projects/{project_id}/pacing/red-lines")
async def get_red_lines(
    project_id: UUID, db: AsyncSession = Depends(get_db),
):
    """Check pacing red line violations."""
    ctrl = PacingController(db)
    violations = await ctrl.check_red_lines(project_id)
    return [
        {
            "rule": v.rule,
            "message": v.message,
            "severity": v.severity,
            "affected_chapters": v.affected_chapters,
        }
        for v in violations
    ]


@router.get("/projects/{project_id}/pacing/suggestion")
async def get_pacing_suggestion(
    project_id: UUID, db: AsyncSession = Depends(get_db),
):
    """Get pacing suggestion for the next chapter."""
    ctrl = PacingController(db)
    suggestion = await ctrl.suggest_next_chapter(project_id)
    return {
        "recommended_strands": suggestion.recommended_strands,
        "recommended_highlights": suggestion.recommended_highlights,
        "tension_suggestion": suggestion.tension_suggestion,
        "target_ratios": suggestion.target_ratios,
    }
