"""Book Rules CRUD API."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, verify_token
from app.engines.rules_engine import GENRE_PROFILES, RulesEngine
from app.models.book_rules import BookRules
from app.schemas.rules import (
    BookRulesResponse,
    BookRulesUpdate,
    GenreListResponse,
    GenreProfileResponse,
    MergedRulesResponse,
)

router = APIRouter(prefix="/api", tags=["rules"], dependencies=[Depends(verify_token)])
_engine = RulesEngine()


@router.get("/rules/genres", response_model=GenreListResponse)
async def list_genre_profiles():
    """List all available genre profiles."""
    genres = [
        GenreProfileResponse(
            name=name,
            zh_name=profile.get("name", name),
            disabled_dimensions=profile.get("disabled_dimensions", []),
            taboos=profile.get("taboos", []),
            settings=profile.get("settings", {}),
        )
        for name, profile in GENRE_PROFILES.items()
    ]
    return GenreListResponse(genres=genres)


@router.get("/projects/{project_id}/rules", response_model=BookRulesResponse)
async def get_book_rules(project_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get book rules for a project."""
    stmt = select(BookRules).where(BookRules.project_id == project_id)
    result = await db.execute(stmt)
    rules = result.scalar_one_or_none()
    if not rules:
        raise HTTPException(
            status_code=404, detail="Book rules not found for this project"
        )
    return BookRulesResponse(
        id=rules.id,
        project_id=rules.project_id,
        base_guardrails=rules.base_guardrails,
        genre_profile=rules.genre_profile,
        custom_rules=rules.custom_rules,
    )


@router.put("/projects/{project_id}/rules", response_model=BookRulesResponse)
async def update_book_rules(
    project_id: UUID,
    body: BookRulesUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update book rules for a project."""
    stmt = select(BookRules).where(BookRules.project_id == project_id)
    result = await db.execute(stmt)
    rules = result.scalar_one_or_none()
    if not rules:
        raise HTTPException(status_code=404, detail="Book rules not found")
    if body.base_guardrails is not None:
        rules.base_guardrails = body.base_guardrails
    if body.genre_profile is not None:
        rules.genre_profile = body.genre_profile
    if body.custom_rules is not None:
        rules.custom_rules = body.custom_rules
    await db.flush()
    return BookRulesResponse(
        id=rules.id,
        project_id=rules.project_id,
        base_guardrails=rules.base_guardrails,
        genre_profile=rules.genre_profile,
        custom_rules=rules.custom_rules,
    )


@router.get(
    "/projects/{project_id}/rules/merged", response_model=MergedRulesResponse
)
async def get_merged_rules(project_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get merged three-layer rules for a project."""
    stmt = select(BookRules).where(BookRules.project_id == project_id)
    result = await db.execute(stmt)
    rules = result.scalar_one_or_none()
    if not rules:
        raise HTTPException(status_code=404, detail="Book rules not found")

    genre = rules.genre_profile.get("name") if rules.genre_profile else None
    merged = _engine.merge(genre=genre, book_rules=rules.custom_rules)
    prompt_text = _engine.format_for_prompt(merged)

    return MergedRulesResponse(
        guardrails=merged["guardrails"],
        taboos=merged["taboos"],
        custom_rules=merged["custom_rules"],
        settings=merged["settings"],
        disabled_dimensions=merged["disabled_dimensions"],
        prompt_text=prompt_text,
    )
