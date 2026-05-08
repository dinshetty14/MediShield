"""Tests for Pydantic models."""

import pytest
from datetime import date

from app.models.document import DocType, CaseStatus, Document, Case
from app.models.agent_outputs import (
    ClassifierOutput,
    KYCOutput,
    ClaimsOutput,
    PolicyOutput,
    FraudOutput,
)
from app.models.decisions import Decision, FinalDecision


class TestDocType:
    def test_from_string_exact_match(self):
        assert DocType.from_string("Patient Bills") == DocType.PATIENT_BILL
        assert DocType.from_string("Claim Forms") == DocType.CLAIM_FORM
        assert DocType.from_string("KYC Documents") == DocType.KYC_DOCUMENT

    def test_from_string_case_insensitive(self):
        assert DocType.from_string("patient bills") == DocType.PATIENT_BILL
        assert DocType.from_string("CLAIM FORMS") == DocType.CLAIM_FORM

    def test_from_string_unknown(self):
        assert DocType.from_string("invalid") == DocType.UNKNOWN
        assert DocType.from_string("") == DocType.UNKNOWN


class TestClassifierOutput:
    def test_create_valid(self):
        output = ClassifierOutput(
            doc_type=DocType.CLAIM_FORM,
            confidence=0.95,
            routing_tags=["claims_queue"],
        )
        assert output.doc_type == DocType.CLAIM_FORM
        assert output.confidence == 0.95
        assert output.agent_name == "classifier"

    def test_confidence_bounds(self):
        # Valid bounds
        output = ClassifierOutput(doc_type=DocType.UNKNOWN, confidence=0.0)
        assert output.confidence == 0.0

        output = ClassifierOutput(doc_type=DocType.UNKNOWN, confidence=1.0)
        assert output.confidence == 1.0

        # Invalid bounds should raise
        with pytest.raises(ValueError):
            ClassifierOutput(doc_type=DocType.UNKNOWN, confidence=1.5)

        with pytest.raises(ValueError):
            ClassifierOutput(doc_type=DocType.UNKNOWN, confidence=-0.1)


class TestKYCOutput:
    def test_create_passed(self):
        output = KYCOutput(
            kyc_passed=True,
            document_type="Aadhaar",
            confidence=0.9,
        )
        assert output.kyc_passed is True
        assert output.is_expired is False

    def test_create_failed_expired(self):
        output = KYCOutput(
            kyc_passed=False,
            document_type="Passport",
            expiry_date=date(2020, 1, 1),
            is_expired=True,
            confidence=0.85,
        )
        assert output.kyc_passed is False
        assert output.is_expired is True


class TestClaimsOutput:
    def test_create_valid_claim(self):
        output = ClaimsOutput(
            claim_amount=15000.50,
            icd_10_codes=["J06.9", "R05"],
            cpt_codes=["99213"],
            provider_name="City Hospital",
            schema_valid=True,
            confidence=0.88,
        )
        assert output.claim_amount == 15000.50
        assert len(output.icd_10_codes) == 2
        assert output.schema_valid is True

    def test_create_invalid_schema(self):
        output = ClaimsOutput(
            schema_valid=False,
            validation_errors=["Missing claim amount", "No ICD codes"],
            confidence=0.5,
        )
        assert output.schema_valid is False
        assert len(output.validation_errors) == 2


class TestFraudOutput:
    def test_low_risk(self):
        output = FraudOutput(
            fraud_score=0.1,
            risk_level="LOW",
            confidence=0.9,
        )
        assert output.fraud_score == 0.1
        assert output.risk_level == "LOW"

    def test_high_risk(self):
        output = FraudOutput(
            fraud_score=0.8,
            risk_level="HIGH",
            anomalies=["Duplicate claim", "Frequency anomaly"],
            duplicate_claim_detected=True,
            confidence=0.85,
        )
        assert output.fraud_score == 0.8
        assert output.duplicate_claim_detected is True


class TestFinalDecision:
    def test_approve_decision(self):
        decision = FinalDecision(
            decision=Decision.APPROVE,
            confidence=0.9,
            justification="All checks passed",
        )
        assert decision.decision == Decision.APPROVE
        assert decision.overridden is False

    def test_get_agent_outputs(self):
        classifier = ClassifierOutput(doc_type=DocType.CLAIM_FORM, confidence=0.9)
        kyc = KYCOutput(kyc_passed=True, confidence=0.85)

        decision = FinalDecision(
            decision=Decision.APPROVE,
            confidence=0.87,
            justification="Approved",
            classifier_output=classifier,
            kyc_output=kyc,
        )

        outputs = decision.get_agent_outputs()
        assert len(outputs) == 2

    def test_min_confidence(self):
        decision = FinalDecision(
            decision=Decision.ESCALATE,
            confidence=0.6,
            justification="Low confidence",
            classifier_output=ClassifierOutput(doc_type=DocType.UNKNOWN, confidence=0.5),
            kyc_output=KYCOutput(kyc_passed=True, confidence=0.9),
        )

        assert decision.min_confidence() == 0.5
