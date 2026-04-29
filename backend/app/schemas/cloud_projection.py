"""
Schemas for cloud projection status and run results.
"""
from typing import Optional

from pydantic import BaseModel


class CloudProjectionRunResult(BaseModel):
    attempted: int
    projected: int
    failed: int
    skipped: int
    message: str


class CloudProjectionStatus(BaseModel):
    unprojected_count: int
    projected_count: int
    failed_count: int
    last_projected_at: Optional[str] = None
