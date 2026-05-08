"""SQLAlchemy database models."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.document import CaseStatus, DocType

from .database import Base


class CaseModel(Base):
    """Database model for cases."""

    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Document info
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column()
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Classification
    status: Mapped[str] = mapped_column(String(20), default=CaseStatus.RECEIVED.value)
    doc_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    queue: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Decision
    decision: Mapped[str | None] = mapped_column(String(20), nullable=True)
    decision_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    decision_justification: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Agent outputs (stored as JSON)
    classifier_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    kyc_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    claims_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    policy_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    fraud_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Override info
    overridden: Mapped[bool] = mapped_column(default=False)
    override_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    override_decision: Mapped[str | None] = mapped_column(String(20), nullable=True)
    override_timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    processing_time_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
