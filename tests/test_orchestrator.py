"""Tests for the Orchestrator Agent."""

import pytest

from app.agents.orchestrator import OrchestratorAgent
from app.models.agent_outputs import (
    ClassifierOutput,
    KYCOutput,
    ClaimsOutput,
    PolicyOutput,
    FraudOutput,
)
from app.models.document import DocType
from app.models.decisions import Decision


@pytest.fixture
def orchestrator():
    return OrchestratorAgent()


@pytest.fixture
def valid_classifier():
    return ClassifierOutput(doc_type=DocType.CLAIM_FORM, confidence=0.9)


@pytest.fixture
def valid_kyc():
    return KYCOutput(kyc_passed=True, confidence=0.85)


@pytest.fixture
def valid_claims():
    return ClaimsOutput(
        claim_amount=10000,
        icd_10_codes=["J06.9"],
        schema_valid=True,
        confidence=0.8,
    )


@pytest.fixture
def valid_policy():
    return PolicyOutput(covered=True, coverage_percentage=80, confidence=0.75)


@pytest.fixture
def low_fraud():
    return FraudOutput(fraud_score=0.1, risk_level="LOW", confidence=0.9)


class TestOrchestratorApprove:
    def test_approve_all_valid(
        self, orchestrator, valid_classifier, valid_kyc, valid_claims, valid_policy, low_fraud
    ):
        """Should approve when all checks pass."""
        result = orchestrator.process(
            classifier_output=valid_classifier,
            kyc_output=valid_kyc,
            claims_output=valid_claims,
            policy_output=valid_policy,
            fraud_output=low_fraud,
        )

        assert result.decision == Decision.APPROVE
        assert result.confidence > 0.7
        assert "passed" in result.justification.lower() or "valid" in result.justification.lower()


class TestOrchestratorReject:
    def test_reject_kyc_failed(
        self, orchestrator, valid_classifier, valid_claims, valid_policy, low_fraud
    ):
        """Should reject when KYC fails."""
        failed_kyc = KYCOutput(kyc_passed=False, confidence=0.9, tampering_flags=["font_mismatch"])

        result = orchestrator.process(
            classifier_output=valid_classifier,
            kyc_output=failed_kyc,
            claims_output=valid_claims,
            policy_output=valid_policy,
            fraud_output=low_fraud,
        )

        assert result.decision == Decision.REJECT
        assert "kyc" in result.justification.lower()

    def test_reject_not_covered(
        self, orchestrator, valid_classifier, valid_kyc, valid_claims, low_fraud
    ):
        """Should reject when procedure not covered."""
        not_covered = PolicyOutput(
            covered=False,
            coverage_percentage=0,
            exclusions=["Pre-existing condition"],
            confidence=0.9,
        )

        result = orchestrator.process(
            classifier_output=valid_classifier,
            kyc_output=valid_kyc,
            claims_output=valid_claims,
            policy_output=not_covered,
            fraud_output=low_fraud,
        )

        assert result.decision == Decision.REJECT
        assert "covered" in result.justification.lower()

    def test_reject_invalid_schema(
        self, orchestrator, valid_classifier, valid_kyc, valid_policy, low_fraud
    ):
        """Should reject when claim schema invalid."""
        invalid_claims = ClaimsOutput(
            schema_valid=False,
            validation_errors=["Missing claim amount"],
            confidence=0.7,
        )

        result = orchestrator.process(
            classifier_output=valid_classifier,
            kyc_output=valid_kyc,
            claims_output=invalid_claims,
            policy_output=valid_policy,
            fraud_output=low_fraud,
        )

        assert result.decision == Decision.REJECT
        assert "schema" in result.justification.lower() or "invalid" in result.justification.lower()


class TestOrchestratorEscalate:
    def test_escalate_high_fraud(
        self, orchestrator, valid_classifier, valid_kyc, valid_claims, valid_policy
    ):
        """Should escalate when fraud score is high."""
        high_fraud = FraudOutput(
            fraud_score=0.5,
            risk_level="MEDIUM",
            anomalies=["Duplicate submission suspected"],
            confidence=0.8,
        )

        result = orchestrator.process(
            classifier_output=valid_classifier,
            kyc_output=valid_kyc,
            claims_output=valid_claims,
            policy_output=valid_policy,
            fraud_output=high_fraud,
        )

        assert result.decision == Decision.ESCALATE
        assert "fraud" in result.justification.lower()

    def test_escalate_low_confidence(
        self, orchestrator, valid_kyc, valid_claims, valid_policy, low_fraud
    ):
        """Should escalate when any agent has low confidence."""
        low_conf_classifier = ClassifierOutput(doc_type=DocType.CLAIM_FORM, confidence=0.4)

        result = orchestrator.process(
            classifier_output=low_conf_classifier,
            kyc_output=valid_kyc,
            claims_output=valid_claims,
            policy_output=valid_policy,
            fraud_output=low_fraud,
        )

        assert result.decision == Decision.ESCALATE
        assert "confidence" in result.justification.lower()


class TestOrchestratorEdgeCases:
    def test_minimal_inputs(self, orchestrator):
        """Should handle minimal inputs gracefully."""
        result = orchestrator.process()

        # Should still return a decision
        assert result.decision in [Decision.APPROVE, Decision.REJECT, Decision.ESCALATE]

    def test_only_classifier(self, orchestrator, valid_classifier):
        """Should handle only classifier output."""
        result = orchestrator.process(classifier_output=valid_classifier)

        assert result.decision is not None
        assert result.classifier_output == valid_classifier
