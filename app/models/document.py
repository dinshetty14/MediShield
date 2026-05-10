"""Document and Case models."""

from datetime import datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class DocType(str, Enum):
    """Document type categories."""

    PATIENT_BILL = "Patient Bills"
    CLAIM_FORM = "Claim Forms"
    KYC_DOCUMENT = "KYC Documents"
    MEDICAL_REPORT = "Medical Reports"
    PRESCRIPTION = "Prescriptions"
    POLICY_DOCUMENT = "Policy Documents"  # Insurance policy PDFs for RAG ingestion
    UNKNOWN = "Unknown"

    @classmethod
    def from_string(cls, value: str) -> "DocType":
        """Convert string to DocType (case-insensitive)."""
        value_lower = value.lower().strip()
        for doc_type in cls:
            if doc_type.value.lower() == value_lower:
                return doc_type
        return cls.UNKNOWN


class CaseStatus(str, Enum):
    """Case processing status."""

    RECEIVED = "received"
    PROCESSING = "processing"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


class Document(BaseModel):
    """Represents an uploaded document."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    filename: str
    content_type: str
    size_bytes: int
    upload_timestamp: datetime = Field(default_factory=datetime.utcnow)
    storage_path: str | None = None


class Case(BaseModel):
    """Represents a document processing case."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    document: Document
    status: CaseStatus = CaseStatus.RECEIVED
    doc_type: DocType | None = None
    queue: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    processing_time_seconds: float | None = None

    def update_status(self, status: CaseStatus) -> None:
        """Update case status and timestamp."""
        self.status = status
        self.updated_at = datetime.utcnow()
