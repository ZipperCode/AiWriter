"""Schemas for human-in-the-loop."""

from pydantic import BaseModel


class HumanLoopApproval(BaseModel):
    action: str  # "approve" | "reject" | "edit"
    content: str | None = None


class HumanLoopStatus(BaseModel):
    loop_id: str
    node_name: str
    status: str  # "pending" | "approved" | "rejected"
    data: dict = {}
