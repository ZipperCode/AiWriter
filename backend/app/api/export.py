import os
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, verify_token
from app.config import settings
from app.models.project import Project
from app.schemas.export import ExportRequest, ExportResponse
from app.services.export_service import ExportService

router = APIRouter(
    prefix="/api/projects", tags=["export"], dependencies=[Depends(verify_token)]
)


@router.post("/{project_id}/export", response_model=ExportResponse)
async def export_project(
    project_id: UUID,
    request: ExportRequest,
    db: AsyncSession = Depends(get_db),
):
    """Export a project in the specified format (txt, markdown, or epub)."""
    # Validate format
    valid_formats = ["txt", "markdown", "epub"]
    if request.format not in valid_formats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid format. Must be one of: {', '.join(valid_formats)}",
        )

    # Check if project exists
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Create export service and export
    service = ExportService(db, storage_dir=settings.storage_dir)

    try:
        if request.format == "txt":
            filepath = await service.export_txt(project_id)
            extension = "txt"
        elif request.format == "markdown":
            filepath = await service.export_markdown(project_id)
            extension = "md"
        elif request.format == "epub":
            filepath = await service.export_epub(project_id)
            extension = "epub"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid format",
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(e)}",
        )

    # Return response with download URL
    filename = os.path.basename(filepath)
    download_url = f"/api/export/download/{filename}"

    return ExportResponse(
        file_path=filepath,
        format=request.format,
        download_url=download_url,
    )


@router.get("/export/download/{filename}", dependencies=[Depends(verify_token)])
async def download_export(filename: str):
    """Download an exported file."""
    filepath = os.path.join(settings.storage_dir, "exports", filename)

    # Validate path (prevent directory traversal)
    if not os.path.exists(filepath) or not os.path.isfile(filepath):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    # Ensure the file is within the exports directory
    real_path = os.path.realpath(filepath)
    export_dir = os.path.realpath(os.path.join(settings.storage_dir, "exports"))
    if not real_path.startswith(export_dir):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return FileResponse(filepath, filename=os.path.basename(filepath))
