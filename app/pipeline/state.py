"""Pipeline state definition for LangGraph."""

from typing import TypedDict

from app.models.agent_outputs import (
    ClaimsOutput,
    ClassifierOutput,
    FraudOutput,
    KYCOutput,
    PolicyIngestionOutput,
    PolicyOutput,
)
from app.models.decisions import FinalDecision
from app.models.document import DocType


class PipelineState(TypedDict, total=False):
    """State that flows through the LangGraph pipeline.

    All fields are optional (total=False) to allow incremental updates.
    """

    # Input
    case_id: str
    image_bytes: bytes
    image_path: str

    # Classification
    doc_type: DocType | None

    # Agent outputs
    classifier_output: ClassifierOutput | None
    kyc_output: KYCOutput | None
    claims_output: ClaimsOutput | None
    policy_output: PolicyOutput | None
    fraud_output: FraudOutput | None
    policy_ingestion_output: PolicyIngestionOutput | None

    # Final decision
    final_decision: FinalDecision | None

    # Error handling
    error: str | None
    current_step: str
