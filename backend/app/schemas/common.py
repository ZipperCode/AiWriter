from pydantic import BaseModel


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int = 1
    page_size: int = 20


class ErrorResponse(BaseModel):
    error: dict  # {"code": str, "message": str, "details": any}
