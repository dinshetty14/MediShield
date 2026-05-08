"""Fraud Detection Agent - analyzes claims for fraud indicators."""

import time
from datetime import date, timedelta

from app.models.agent_outputs import ClaimsOutput, FraudOutput

from .base import BaseAgent


# Simulated claim history database
# In production, this would query a real database
_CLAIM_HISTORY: dict[str, list[dict]] = {}


FRAUD_ANALYSIS_PROMPT = """You are a fraud detection specialist for MediShield Insurance.

Analyze the following claim and patient history for potential fraud indicators.

CURRENT CLAIM:
{current_claim}

PATIENT CLAIM HISTORY (last 12 months):
{claim_history}

Check for the following fraud patterns:
1. Duplicate Claims: Same procedure/diagnosis submitted multiple times
2. Frequency Anomalies: Unusually high number of claims in short period
3. Provider Patterns: Suspicious billing patterns or known fraudulent providers
4. Amount Anomalies: Claim amounts significantly higher than typical
5. Date Manipulation: Service dates that don't align with treatment patterns
6. Unbundling: Related procedures billed separately to inflate costs

Respond with a JSON object:
```json
{{
  "fraud_score": <float 0.0-1.0, higher = more suspicious>,
  "risk_level": "<LOW, MEDIUM, or HIGH>",
  "anomalies": ["<list of detected anomalies>"],
  "duplicate_claim_detected": <true or false>,
  "frequency_anomaly": <true or false>,
  "provider_pattern_flag": <true or false>,
  "reasoning": "<explanation of fraud assessment>",
  "confidence": <float between 0 and 1>
}}
```

Scoring Guide:
- 0.0-0.3: LOW risk - typical claim patterns
- 0.3-0.6: MEDIUM risk - some anomalies detected
- 0.6-1.0: HIGH risk - significant fraud indicators
"""


class FraudAgent(BaseAgent):
    """Agent that detects potential fraud in claims."""

    def process(
        self,
        claims_output: ClaimsOutput | None = None,
        patient_id: str | None = None,
        provider_name: str | None = None,
    ) -> FraudOutput:
        """Analyze a claim for fraud indicators.

        Args:
            claims_output: Output from ClaimsAgent
            patient_id: Patient identifier for history lookup
            provider_name: Provider name for pattern checking

        Returns:
            FraudOutput with fraud score and anomalies
        """
        start_time = time.perf_counter()

        try:
            # Format current claim info
            current_claim = self._format_current_claim(claims_output)

            # Get patient claim history
            claim_history = self._get_claim_history(patient_id)
            history_str = self._format_claim_history(claim_history)

            # Run rule-based checks first
            rule_based_flags = self._run_rule_based_checks(
                claims_output, claim_history
            )

            # Call LLM for comprehensive analysis
            prompt = FRAUD_ANALYSIS_PROMPT.format(
                current_claim=current_claim,
                claim_history=history_str,
            )

            response = self._call_with_retry(self._call_llm, prompt)
            result = self._parse_json_response(response)
            elapsed = time.perf_counter() - start_time

            # Combine LLM analysis with rule-based checks
            fraud_score = float(result.get("fraud_score", 0.0))
            anomalies = result.get("anomalies", [])

            # Add rule-based anomalies
            if rule_based_flags["duplicate"]:
                fraud_score = max(fraud_score, 0.7)
                if "Duplicate claim detected" not in anomalies:
                    anomalies.append("Duplicate claim detected (rule-based)")

            if rule_based_flags["frequency"]:
                fraud_score = max(fraud_score, 0.5)
                if "High claim frequency" not in str(anomalies):
                    anomalies.append("High claim frequency detected (rule-based)")

            # Determine risk level
            if fraud_score >= 0.6:
                risk_level = "HIGH"
            elif fraud_score >= 0.3:
                risk_level = "MEDIUM"
            else:
                risk_level = "LOW"

            output = FraudOutput(
                fraud_score=min(max(fraud_score, 0.0), 1.0),
                risk_level=risk_level,
                anomalies=anomalies,
                duplicate_claim_detected=result.get("duplicate_claim_detected", False) or rule_based_flags["duplicate"],
                frequency_anomaly=result.get("frequency_anomaly", False) or rule_based_flags["frequency"],
                provider_pattern_flag=result.get("provider_pattern_flag", False),
                confidence=min(max(float(result.get("confidence", 0.7)), 0.0), 1.0),
                processing_time_seconds=elapsed,
            )
            print(f"  [Fraud] Result: score={output.fraud_score}, risk={output.risk_level}, confidence={output.confidence}")
            return output

        except Exception as e:
            elapsed = time.perf_counter() - start_time
            print(f"  [Fraud] ERROR: {type(e).__name__}: {e}")
            # On error, return conservative estimate (low risk)
            return FraudOutput(
                fraud_score=0.1,
                risk_level="LOW",
                anomalies=[],
                confidence=0.7,  # Higher confidence to not trigger escalation
                processing_time_seconds=elapsed,
                errors=[str(e)],
            )

    def _format_current_claim(self, claims_output: ClaimsOutput | None) -> str:
        """Format current claim for the prompt."""
        if not claims_output:
            return "No claim details provided"

        parts = []
        if claims_output.claim_amount:
            parts.append(f"Amount: {claims_output.currency} {claims_output.claim_amount}")
        if claims_output.diagnosis:
            parts.append(f"Diagnosis: {claims_output.diagnosis}")
        if claims_output.icd_10_codes:
            parts.append(f"ICD-10 Codes: {', '.join(claims_output.icd_10_codes)}")
        if claims_output.cpt_codes:
            parts.append(f"CPT Codes: {', '.join(claims_output.cpt_codes)}")
        if claims_output.provider_name:
            parts.append(f"Provider: {claims_output.provider_name}")
        if claims_output.service_date:
            parts.append(f"Service Date: {claims_output.service_date}")

        return "\n".join(parts) if parts else "Minimal claim details"

    def _get_claim_history(self, patient_id: str | None) -> list[dict]:
        """Get patient claim history from database."""
        if not patient_id:
            return []

        # In production, this would query a real database
        return _CLAIM_HISTORY.get(patient_id, [])

    def _format_claim_history(self, history: list[dict]) -> str:
        """Format claim history for the prompt."""
        if not history:
            return "No prior claims in the last 12 months"

        parts = []
        for i, claim in enumerate(history[-10:], 1):  # Last 10 claims
            parts.append(
                f"{i}. Date: {claim.get('date', 'N/A')}, "
                f"Amount: {claim.get('amount', 'N/A')}, "
                f"Diagnosis: {claim.get('diagnosis', 'N/A')}"
            )

        return "\n".join(parts)

    def _run_rule_based_checks(
        self,
        claims_output: ClaimsOutput | None,
        history: list[dict],
    ) -> dict[str, bool]:
        """Run rule-based fraud checks."""
        flags = {
            "duplicate": False,
            "frequency": False,
        }

        if not claims_output:
            return flags

        # Check for duplicates (same ICD codes within 7 days)
        if claims_output.icd_10_codes and history:
            current_codes = set(claims_output.icd_10_codes)
            for prev_claim in history:
                prev_codes = set(prev_claim.get("icd_codes", []))
                if current_codes & prev_codes:  # Intersection
                    prev_date = prev_claim.get("date")
                    if prev_date and claims_output.service_date:
                        days_diff = abs((claims_output.service_date - prev_date).days)
                        if days_diff < 7:
                            flags["duplicate"] = True
                            break

        # Check frequency (more than 5 claims in 30 days)
        if history:
            thirty_days_ago = date.today() - timedelta(days=30)
            recent_claims = [
                c for c in history
                if c.get("date") and c["date"] >= thirty_days_ago
            ]
            if len(recent_claims) > 5:
                flags["frequency"] = True

        return flags

    @staticmethod
    def add_to_history(patient_id: str, claim_data: dict) -> None:
        """Add a claim to patient history (for testing/simulation)."""
        if patient_id not in _CLAIM_HISTORY:
            _CLAIM_HISTORY[patient_id] = []
        _CLAIM_HISTORY[patient_id].append(claim_data)

    @staticmethod
    def clear_history(patient_id: str | None = None) -> None:
        """Clear claim history (for testing)."""
        if patient_id:
            _CLAIM_HISTORY.pop(patient_id, None)
        else:
            _CLAIM_HISTORY.clear()
