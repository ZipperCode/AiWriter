from pydantic import BaseModel, Field


class ExportRequest(BaseModel):
    """Request model for export endpoint."""

    format: str = Field(..., description="Export format: txt, markdown, or epub")


class ExportResponse(BaseModel):
    """Response model for export endpoint."""

    file_path: str = Field(..., description="Path to the exported file")
    format: str = Field(..., description="Export format")
    download_url: str = Field(..., description="URL to download the exported file")
