from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, verify_token
from app.models.chapter import Chapter
from app.models.project import Project
from app.schemas.chapter import ChapterCreate, ChapterResponse, ChapterUpdate

router = APIRouter(tags=["chapters"], dependencies=[Depends(verify_token)])


@router.get("/api/projects/{project_id}/chapters", response_model=dict)
async def list_chapters(
    project_id: UUID,
    volume_id: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    base_filter = Chapter.project_id == project_id
    if volume_id:
        base_filter = base_filter & (Chapter.volume_id == volume_id)

    total_q = await db.execute(select(func.count(Chapter.id)).where(base_filter))
    total = total_q.scalar_one()
    q = (
        select(Chapter)
        .where(base_filter)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .order_by(Chapter.sort_order)
    )
    result = await db.execute(q)
    items = [ChapterResponse.model_validate(c) for c in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post(
    "/api/projects/{project_id}/chapters",
    response_model=ChapterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_chapter(
    project_id: UUID, data: ChapterCreate, db: AsyncSession = Depends(get_db)
):
    proj = await db.execute(select(Project).where(Project.id == project_id))
    if not proj.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    chapter = Chapter(project_id=project_id, **data.model_dump())
    db.add(chapter)
    await db.flush()
    await db.refresh(chapter)
    return ChapterResponse.model_validate(chapter)


@router.get("/api/chapters/{chapter_id}", response_model=ChapterResponse)
async def get_chapter(chapter_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return ChapterResponse.model_validate(chapter)


@router.put("/api/chapters/{chapter_id}", response_model=ChapterResponse)
async def update_chapter(
    chapter_id: UUID, data: ChapterUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(chapter, field, value)
    await db.flush()
    await db.refresh(chapter)
    return ChapterResponse.model_validate(chapter)
