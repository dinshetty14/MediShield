"""Decision models for the orchestrator."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from .agent_outputs import (
    AgentOutput,
    ClaimsOutput,
    ClassifierOutput,
    FraudOutput,
    KYCOutput,
    PolicyOutput,
)


class Decision(str, Enum):
    """Final decision types."""

    APPROVE = "approve"
    REJECT = "reject"
    ESCALATE = "escalate"


class FinalDecision(BaseModel):
    """Final decision from the Orchestrator Agent."""

    decision: Decision
    confidence: float = Field(ge=0.0, le=1.0)
    justification: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Agent summaries
    classifier_output: ClassifierOutput | None = None
    kyc_output: KYCOutput | None = None
    claims_output: ClaimsOutput | None = None
    policy_output: PolicyOutput | None = None
    fraud_output: FraudOutput | None = None

    # Override information (for human review)
    overridden: bool = False
    override_by: str | None = None
    override_reason: str | None = None
    override_timestamp: datetime | None = None

    def get_agent_outputs(self) -> list[AgentOutput]:
        """Return all non-null agent outputs."""
        outputs = []
        for output in [
            self.classifier_output,
            self.kyc_output,
            self.claims_output,
            self.policy_output,
            self.fraud_output,
        ]:
            if output is not None:
                outputs.append(output)
        return outputs

    def min_confidence(self) -> float:
        """Return the minimum confidence across all agents."""
        confidences = [o.confidence for o in self.get_agent_outputs()]
        return min(confidences) if confidences else 0.0
