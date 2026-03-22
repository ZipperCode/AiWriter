from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, verify_token
from app.models.entity import Entity
from app.models.project import Project
from app.models.relationship import Relationship
from app.schemas.entity import (
    EntityCreate,
    EntityResponse,
    EntityUpdate,
    RelationshipCreate,
    RelationshipResponse,
)

router = APIRouter(tags=["entities"], dependencies=[Depends(verify_token)])


# --- Entity CRUD ---


@router.get("/api/projects/{project_id}/entities", response_model=dict)
async def list_entities(
    project_id: UUID,
    entity_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    base_filter = Entity.project_id == project_id
    if entity_type:
        base_filter = base_filter & (Entity.entity_type == entity_type)

    total_q = await db.execute(select(func.count(Entity.id)).where(base_filter))
    total = total_q.scalar_one()
    q = (
        select(Entity)
        .where(base_filter)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .order_by(Entity.created_at.desc())
    )
    result = await db.execute(q)
    items = [EntityResponse.model_validate(e) for e in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post(
    "/api/projects/{project_id}/entities",
    response_model=EntityResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_entity(
    project_id: UUID, data: EntityCreate, db: AsyncSession = Depends(get_db)
):
    proj = await db.execute(select(Project).where(Project.id == project_id))
    if not proj.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    entity = Entity(project_id=project_id, **data.model_dump())
    db.add(entity)
    await db.flush()
    await db.refresh(entity)
    return EntityResponse.model_validate(entity)


@router.get("/api/entities/{entity_id}", response_model=EntityResponse)
async def get_entity(entity_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return EntityResponse.model_validate(entity)


@router.put("/api/entities/{entity_id}", response_model=EntityResponse)
async def update_entity(
    entity_id: UUID, data: EntityUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(entity, field, value)
    await db.flush()
    await db.refresh(entity)
    return EntityResponse.model_validate(entity)


@router.delete("/api/entities/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entity(entity_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    await db.delete(entity)


# --- Relationship CRUD ---


@router.get("/api/projects/{project_id}/relationships", response_model=dict)
async def list_relationships(
    project_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    total_q = await db.execute(
        select(func.count(Relationship.id)).where(Relationship.project_id == project_id)
    )
    total = total_q.scalar_one()
    q = (
        select(Relationship)
        .where(Relationship.project_id == project_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .order_by(Relationship.created_at.desc())
    )
    result = await db.execute(q)
    items = [RelationshipResponse.model_validate(r) for r in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post(
    "/api/projects/{project_id}/relationships",
    response_model=RelationshipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_relationship(
    project_id: UUID, data: RelationshipCreate, db: AsyncSession = Depends(get_db)
):
    proj = await db.execute(select(Project).where(Project.id == project_id))
    if not proj.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    rel = Relationship(project_id=project_id, **data.model_dump())
    db.add(rel)
    await db.flush()
    await db.refresh(rel)
    return RelationshipResponse.model_validate(rel)


# Graph query — deferred to iteration 2
@router.get("/api/projects/{project_id}/graph")
async def graph_query(project_id: UUID):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Graph query will be implemented in iteration 2",
    )
