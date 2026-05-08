"""API request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class CaseCreate(BaseModel):
    """Schema for case creation (file upload handled separately)."""
    pass


class CaseResponse(BaseModel):
    """Schema for case response."""

    id: str
    filename: str
    content_type: str
    size_bytes: int
    status: str
    doc_type: str | None = None
    queue: str | None = None
    decision: str | None = None
    decision_confidence: float | None = None
    decision_justification: str | None = None
    processing_time_seconds: float | None = None
    created_at: datetime
    updated_at: datetime

    # Override info
    overridden: bool = False
    override_by: str | None = None
    override_reason: str | None = None
    override_decision: str | None = None

    class Config:
        from_attributes = True


class CaseDetailResponse(CaseResponse):
    """Detailed case response including agent outputs."""

    classifier_output: dict | None = None
    kyc_output: dict | None = None
    claims_output: dict | None = None
    policy_output: dict | None = None
    fraud_output: dict | None = None


class CaseListResponse(BaseModel):
    """Schema for case list response."""

    cases: list[CaseResponse]
    total: int
    limit: int
    offset: int


class OverrideRequest(BaseModel):
    """Schema for decision override request."""

    decision: str = Field(..., pattern="^(approve|reject)$")
    override_by: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=10)


class StatsResponse(BaseModel):
    """Schema for statistics response."""

    total: int
    by_status: dict[str, int]


class HealthResponse(BaseModel):
    """Schema for health check response."""

    status: str
    version: str
    database: str
