from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, verify_token
from app.models.volume import Volume
from app.models.project import Project
from app.schemas.volume import VolumeCreate, VolumeResponse, VolumeUpdate

router = APIRouter(tags=["volumes"], dependencies=[Depends(verify_token)])


@router.get("/api/projects/{project_id}/volumes", response_model=dict)
async def list_volumes(
    project_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    total_q = await db.execute(
        select(func.count(Volume.id)).where(Volume.project_id == project_id)
    )
    total = total_q.scalar_one()
    q = (
        select(Volume)
        .where(Volume.project_id == project_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .order_by(Volume.sort_order)
    )
    result = await db.execute(q)
    items = [VolumeResponse.model_validate(v) for v in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post(
    "/api/projects/{project_id}/volumes",
    response_model=VolumeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_volume(
    project_id: UUID, data: VolumeCreate, db: AsyncSession = Depends(get_db)
):
    # Verify project exists
    proj = await db.execute(select(Project).where(Project.id == project_id))
    if not proj.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    volume = Volume(project_id=project_id, **data.model_dump())
    db.add(volume)
    await db.flush()
    await db.refresh(volume)
    return VolumeResponse.model_validate(volume)


@router.get("/api/volumes/{volume_id}", response_model=VolumeResponse)
async def get_volume(volume_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Volume).where(Volume.id == volume_id))
    volume = result.scalar_one_or_none()
    if not volume:
        raise HTTPException(status_code=404, detail="Volume not found")
    return VolumeResponse.model_validate(volume)


@router.put("/api/volumes/{volume_id}", response_model=VolumeResponse)
async def update_volume(
    volume_id: UUID, data: VolumeUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Volume).where(Volume.id == volume_id))
    volume = result.scalar_one_or_none()
    if not volume:
        raise HTTPException(status_code=404, detail="Volume not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(volume, field, value)
    await db.flush()
    await db.refresh(volume)
    return VolumeResponse.model_validate(volume)


@router.delete("/api/volumes/{volume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_volume(volume_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Volume).where(Volume.id == volume_id))
    volume = result.scalar_one_or_none()
    if not volume:
        raise HTTPException(status_code=404, detail="Volume not found")
    await db.delete(volume)
