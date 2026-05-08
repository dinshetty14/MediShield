"""Claims Agent - extracts structured data from claim documents."""

import time
from datetime import date, datetime
from pathlib import Path

from app.models.agent_outputs import ClaimsOutput

from .base import BaseAgent


CLAIMS_PROMPT = """You are a claims data extraction specialist for MediShield Insurance.

Analyze this document image and extract all claim-related information. This could be a:
- Claim form
- Hospital bill
- Medical report
- Prescription

Extract the following fields (use null for fields not found):

Respond with a JSON object in this exact format:
```json
{
  "claim_amount": <float or null>,
  "currency": "<INR, USD, etc. - default INR>",
  "icd_10_codes": ["<diagnosis codes>"],
  "cpt_codes": ["<procedure codes>"],
  "provider_name": "<hospital or clinic name or null>",
  "provider_npi": "<NPI number if visible or null>",
  "patient_name": "<patient name or null>",
  "service_date": "<YYYY-MM-DD or null>",
  "diagnosis": "<primary diagnosis description or null>",
  "line_items": [
    {"description": "<item>", "amount": <float>}
  ],
  "confidence": <float between 0 and 1>,
  "extraction_notes": "<any issues or notes about extraction>"
}
```

ICD-10 Code Format: Letter followed by 2+ digits (e.g., J06.9, M54.5, E11.9)
CPT Code Format: 5-digit numeric codes (e.g., 99213, 99214, 70553)

If no medical codes are visible, check for:
- Diagnosis descriptions that can be mapped to ICD-10
- Procedure descriptions that suggest CPT codes

Set confidence based on:
- 0.9-1.0: All key fields clearly visible and extracted
- 0.7-0.9: Most fields extracted, some inferred
- 0.5-0.7: Partial extraction, some fields unclear
- Below 0.5: Significant extraction issues
"""


class ClaimsAgent(BaseAgent):
    """Agent that extracts claim data from documents."""

    def process(
        self,
        image_source: bytes | str | Path,
    ) -> ClaimsOutput:
        """Extract claim data from a document.

        Args:
            image_source: Image bytes, file path, or Path object

        Returns:
            ClaimsOutput with extracted fields
        """
        start_time = time.perf_counter()

        try:
            response = self._call_with_retry(
                self._call_vision_llm,
                image_source,
                CLAIMS_PROMPT,
            )

            result = self._parse_json_response(response)
            elapsed = time.perf_counter() - start_time

            # Validate and clean extracted data
            claim_amount = result.get("claim_amount")
            if claim_amount is not None:
                try:
                    claim_amount = float(claim_amount)
                except (ValueError, TypeError):
                    claim_amount = None

            icd_codes = self._validate_icd_codes(result.get("icd_10_codes", []))
            cpt_codes = self._validate_cpt_codes(result.get("cpt_codes", []))

            # Validate schema - only require claim_amount for bills
            # ICD-10 codes are optional (not present on patient bills)
            validation_errors = []
            schema_valid = True

            if claim_amount is None:
                validation_errors.append("claim_amount not found")
                schema_valid = False

            # Note: ICD-10 codes are NOT required - patient bills don't have them

            output = ClaimsOutput(
                claim_amount=claim_amount,
                currency=result.get("currency", "INR"),
                icd_10_codes=icd_codes,
                cpt_codes=cpt_codes,
                provider_name=result.get("provider_name"),
                provider_npi=result.get("provider_npi"),
                patient_name=result.get("patient_name"),
                service_date=self._parse_date(result.get("service_date")),
                diagnosis=result.get("diagnosis"),
                schema_valid=schema_valid,
                validation_errors=validation_errors,
                confidence=min(max(float(result.get("confidence", 0.5)), 0.0), 1.0),
                processing_time_seconds=elapsed,
            )
            print(f"  [Claims] Result: amount={claim_amount}, valid={schema_valid}, errors={validation_errors}")
            return output

        except Exception as e:
            elapsed = time.perf_counter() - start_time
            print(f"  [Claims] ERROR: {type(e).__name__}: {e}")
            return ClaimsOutput(
                schema_valid=False,
                validation_errors=[f"extraction_failed: {str(e)}"],
                confidence=0.0,
                processing_time_seconds=elapsed,
                errors=[str(e)],
            )

    def _validate_icd_codes(self, codes: list) -> list[str]:
        """Validate and clean ICD-10 codes."""
        import re

        valid_codes = []
        pattern = re.compile(r"^[A-Z]\d{2}\.?\d*$", re.IGNORECASE)

        for code in codes or []:
            code_str = str(code).strip().upper()
            if pattern.match(code_str):
                valid_codes.append(code_str)

        return valid_codes

    def _validate_cpt_codes(self, codes: list) -> list[str]:
        """Validate and clean CPT codes."""
        import re

        valid_codes = []
        pattern = re.compile(r"^\d{5}$")

        for code in codes or []:
            code_str = str(code).strip()
            if pattern.match(code_str):
                valid_codes.append(code_str)

        return valid_codes

    def _parse_date(self, date_str: str | None) -> date | None:
        """Parse date string to date object."""
        if not date_str:
            return None

        formats = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return None
