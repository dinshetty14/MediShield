"""Agent output schemas."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from .document import DocType


class AgentOutput(BaseModel):
    """Base class for all agent outputs."""

    agent_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    processing_time_seconds: float = 0.0
    errors: list[str] = Field(default_factory=list)


class ClassifierOutput(AgentOutput):
    """Output from the Classifier Agent."""

    agent_name: str = "classifier"
    doc_type: DocType
    routing_tags: list[str] = Field(default_factory=list)


class KYCOutput(AgentOutput):
    """Output from the KYC Agent."""

    agent_name: str = "kyc"
    kyc_passed: bool
    document_type: str | None = None  # Aadhaar, PAN, Passport, etc.
    id_number: str | None = None
    name_on_document: str | None = None
    date_of_birth: date | None = None
    expiry_date: date | None = None
    is_expired: bool = False
    tampering_flags: list[str] = Field(default_factory=list)


class ClaimsOutput(AgentOutput):
    """Output from the Claims Agent."""

    agent_name: str = "claims"
    claim_amount: float | None = None
    currency: str = "INR"
    icd_10_codes: list[str] = Field(default_factory=list)
    cpt_codes: list[str] = Field(default_factory=list)
    provider_name: str | None = None
    provider_npi: str | None = None
    patient_name: str | None = None
    service_date: date | None = None
    diagnosis: str | None = None
    schema_valid: bool = True
    validation_errors: list[str] = Field(default_factory=list)


class PolicyClause(BaseModel):
    """A retrieved policy clause."""

    text: str
    section: str | None = None
    relevance_score: float = 0.0


class PolicyOutput(AgentOutput):
    """Output from the Policy Agent (RAG)."""

    agent_name: str = "policy"
    covered: bool
    coverage_percentage: float = 0.0
    matching_clauses: list[PolicyClause] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    policy_id: str | None = None


class FraudOutput(AgentOutput):
    """Output from the Fraud Detection Agent."""

    agent_name: str = "fraud"
    fraud_score: float = Field(ge=0.0, le=1.0)
    risk_level: str = "LOW"  # LOW, MEDIUM, HIGH
    anomalies: list[str] = Field(default_factory=list)
    duplicate_claim_detected: bool = False
    frequency_anomaly: bool = False
    provider_pattern_flag: bool = False
