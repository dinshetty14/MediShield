"""Orchestrator Agent - aggregates outputs and makes final decision."""

import time
from datetime import datetime

from app.models.agent_outputs import (
    ClassifierOutput,
    ClaimsOutput,
    FraudOutput,
    KYCOutput,
    PolicyOutput,
)
from app.models.decisions import Decision, FinalDecision


# Decision thresholds
FRAUD_SCORE_THRESHOLD = 0.3  # Escalate if >= this
CONFIDENCE_THRESHOLD = 0.6   # Escalate if any agent below this


class OrchestratorAgent:
    """Agent that aggregates all outputs and makes the final decision."""

    def process(
        self,
        classifier_output: ClassifierOutput | None = None,
        kyc_output: KYCOutput | None = None,
        claims_output: ClaimsOutput | None = None,
        policy_output: PolicyOutput | None = None,
        fraud_output: FraudOutput | None = None,
    ) -> FinalDecision:
        """Make final decision based on all agent outputs.

        Decision Logic:
        - REJECT if: KYC failed OR procedure not covered OR schema invalid
        - ESCALATE if: fraud score >= 0.3 OR any agent confidence < 0.6
        - APPROVE if: all checks pass

        Args:
            classifier_output: Output from ClassifierAgent
            kyc_output: Output from KYCAgent
            claims_output: Output from ClaimsAgent
            policy_output: Output from PolicyAgent
            fraud_output: Output from FraudAgent

        Returns:
            FinalDecision with decision, confidence, and justification
        """
        start_time = time.perf_counter()
        reasons = []
        decision = Decision.APPROVE
        confidence_scores = []

        # Collect confidence scores
        if classifier_output:
            confidence_scores.append(classifier_output.confidence)
        if kyc_output:
            confidence_scores.append(kyc_output.confidence)
        if claims_output:
            confidence_scores.append(claims_output.confidence)
        if policy_output:
            confidence_scores.append(policy_output.confidence)
        if fraud_output:
            confidence_scores.append(fraud_output.confidence)

        # Check for REJECT conditions
        reject_reasons = []

        # KYC check
        if kyc_output and not kyc_output.kyc_passed:
            reject_reasons.append("KYC validation failed")
            if kyc_output.is_expired:
                reject_reasons.append("Identity document expired")
            if kyc_output.tampering_flags:
                reject_reasons.append(f"Tampering detected: {', '.join(kyc_output.tampering_flags)}")

        # Schema validation check
        if claims_output and not claims_output.schema_valid:
            reject_reasons.append(f"Invalid claim schema: {', '.join(claims_output.validation_errors)}")

        # Policy coverage check
        if policy_output and not policy_output.covered:
            reject_reasons.append("Procedure not covered by policy")
            if policy_output.exclusions:
                reject_reasons.append(f"Exclusions: {', '.join(policy_output.exclusions)}")

        if reject_reasons:
            decision = Decision.REJECT
            reasons.extend(reject_reasons)

        # Check for ESCALATE conditions (only if not already rejected)
        escalate_reasons = []

        if decision != Decision.REJECT:
            # Fraud score check
            if fraud_output and fraud_output.fraud_score >= FRAUD_SCORE_THRESHOLD:
                escalate_reasons.append(
                    f"High fraud risk (score: {fraud_output.fraud_score:.2f}, "
                    f"level: {fraud_output.risk_level})"
                )
                if fraud_output.anomalies:
                    escalate_reasons.append(f"Anomalies: {', '.join(fraud_output.anomalies[:3])}")

            # Low confidence check
            low_confidence_agents = []
            if classifier_output and classifier_output.confidence < CONFIDENCE_THRESHOLD:
                low_confidence_agents.append(f"classifier ({classifier_output.confidence:.2f})")
            if kyc_output and kyc_output.confidence < CONFIDENCE_THRESHOLD:
                low_confidence_agents.append(f"kyc ({kyc_output.confidence:.2f})")
            if claims_output and claims_output.confidence < CONFIDENCE_THRESHOLD:
                low_confidence_agents.append(f"claims ({claims_output.confidence:.2f})")
            if policy_output and policy_output.confidence < CONFIDENCE_THRESHOLD:
                low_confidence_agents.append(f"policy ({policy_output.confidence:.2f})")

            if low_confidence_agents:
                escalate_reasons.append(
                    f"Low confidence in: {', '.join(low_confidence_agents)}"
                )

            if escalate_reasons:
                decision = Decision.ESCALATE
                reasons.extend(escalate_reasons)

        # If APPROVE, add positive reasons
        if decision == Decision.APPROVE:
            if kyc_output and kyc_output.kyc_passed:
                reasons.append("KYC validation passed")
            if claims_output and claims_output.schema_valid:
                reasons.append("Claim schema valid")
            if policy_output and policy_output.covered:
                coverage = policy_output.coverage_percentage
                reasons.append(f"Procedure covered ({coverage:.0f}% coverage)")
            if fraud_output:
                reasons.append(f"Fraud risk: {fraud_output.risk_level} ({fraud_output.fraud_score:.2f})")

            if not reasons:
                reasons.append("All checks passed")

        # Calculate overall confidence
        if confidence_scores:
            overall_confidence = sum(confidence_scores) / len(confidence_scores)
            # Reduce confidence for escalated cases
            if decision == Decision.ESCALATE:
                overall_confidence *= 0.8
        else:
            overall_confidence = 0.5

        elapsed = time.perf_counter() - start_time

        return FinalDecision(
            decision=decision,
            confidence=min(max(overall_confidence, 0.0), 1.0),
            justification=" | ".join(reasons),
            timestamp=datetime.utcnow(),
            classifier_output=classifier_output,
            kyc_output=kyc_output,
            claims_output=claims_output,
            policy_output=policy_output,
            fraud_output=fraud_output,
        )
