"""Rule-based Fraud Detection Agent - no LLM required."""

import time
from datetime import date, timedelta
from statistics import mean, stdev

from app.models.agent_outputs import ClaimsOutput, FraudOutput


# Simulated patient claim history database
_CLAIM_HISTORY: dict[str, list[dict]] = {}


# Fraud detection thresholds
DUPLICATE_WINDOW_DAYS = 7
FREQUENCY_WINDOW_DAYS = 30
FREQUENCY_THRESHOLD = 5
AMOUNT_MULTIPLIER = 2.0  # Flag if > 2x average


class RuleFraudAgent:
    """Rule-based fraud detection agent."""

    def process(
        self,
        claims_output: ClaimsOutput | None = None,
        patient_id: str | None = None,
    ) -> FraudOutput:
        """Analyze claim for fraud using rule-based checks.

        Checks:
        1. Duplicate submission (same amount within 7 days)
        2. Frequency anomaly (> 5 claims in 30 days)
        3. Amount anomaly (> 2x historical average)

        Returns:
            FraudOutput with fraud score and detected anomalies
        """
        start_time = time.perf_counter()

        anomalies = []
        fraud_score = 0.0

        # Get claim details
        claim_amount = claims_output.claim_amount if claims_output else None
        service_date = claims_output.service_date if claims_output else date.today()
        icd_codes = claims_output.icd_10_codes if claims_output else []

        # Get patient history
        history = self._get_history(patient_id)

        # Check 1: Duplicate submission
        if claim_amount and self._check_duplicate(claim_amount, service_date, icd_codes, history):
            anomalies.append("Potential duplicate claim detected")
            fraud_score += 0.4

        # Check 2: Frequency anomaly
        if self._check_frequency(history):
            anomalies.append(f"High claim frequency (>{FREQUENCY_THRESHOLD} in {FREQUENCY_WINDOW_DAYS} days)")
            fraud_score += 0.3

        # Check 3: Amount anomaly
        if claim_amount and self._check_amount_anomaly(claim_amount, history):
            anomalies.append(f"Claim amount unusually high (>{AMOUNT_MULTIPLIER}x average)")
            fraud_score += 0.2

        # Determine risk level
        if fraud_score >= 0.5:
            risk_level = "HIGH"
        elif fraud_score >= 0.3:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        elapsed = time.perf_counter() - start_time
        print(f"  [RuleFraud] Result: score={fraud_score:.2f}, risk={risk_level}, anomalies={len(anomalies)}")

        return FraudOutput(
            fraud_score=min(fraud_score, 1.0),
            risk_level=risk_level,
            anomalies=anomalies,
            duplicate_claim_detected=any("duplicate" in a.lower() for a in anomalies),
            frequency_anomaly=any("frequency" in a.lower() for a in anomalies),
            provider_pattern_flag=False,
            confidence=0.9,  # High confidence for rule-based
            processing_time_seconds=elapsed,
        )

    def _get_history(self, patient_id: str | None) -> list[dict]:
        """Get patient claim history."""
        if not patient_id:
            return []
        return _CLAIM_HISTORY.get(patient_id, [])

    def _check_duplicate(
        self,
        amount: float,
        service_date: date | None,
        icd_codes: list[str],
        history: list[dict],
    ) -> bool:
        """Check for duplicate claim submission."""
        if not history:
            return False

        service_date = service_date or date.today()
        window_start = service_date - timedelta(days=DUPLICATE_WINDOW_DAYS)

        for prev in history:
            prev_date = prev.get("date")
            prev_amount = prev.get("amount")
            prev_codes = set(prev.get("icd_codes", []))

            if not prev_date or not prev_amount:
                continue

            # Check if within window
            if prev_date < window_start:
                continue

            # Check for similar claim
            amount_match = abs(prev_amount - amount) < 1.0  # Within 1 unit
            code_overlap = bool(set(icd_codes) & prev_codes) if icd_codes and prev_codes else False

            if amount_match or code_overlap:
                return True

        return False

    def _check_frequency(self, history: list[dict]) -> bool:
        """Check for abnormal claim frequency."""
        if not history:
            return False

        window_start = date.today() - timedelta(days=FREQUENCY_WINDOW_DAYS)
        recent_claims = [h for h in history if h.get("date") and h["date"] >= window_start]

        return len(recent_claims) > FREQUENCY_THRESHOLD

    def _check_amount_anomaly(self, amount: float, history: list[dict]) -> bool:
        """Check if amount is abnormally high compared to history."""
        if not history or len(history) < 3:
            return False  # Not enough history to compare

        amounts = [h.get("amount") for h in history if h.get("amount")]
        if not amounts:
            return False

        avg = mean(amounts)
        return amount > (avg * AMOUNT_MULTIPLIER)

    @staticmethod
    def add_to_history(patient_id: str, claim_data: dict) -> None:
        """Add a claim to patient history (for testing)."""
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
