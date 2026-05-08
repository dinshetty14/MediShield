"""KYC Agent - validates identity documents."""

import time
from datetime import date, datetime
from pathlib import Path

from app.models.agent_outputs import KYCOutput

from .base import BaseAgent


KYC_PROMPT = """You are a KYC (Know Your Customer) validation specialist for MediShield Insurance.

Analyze this identity document image and extract all relevant information. Check for:
1. Document authenticity indicators
2. Expiry date validation
3. Visual anomalies that might indicate tampering

Respond with a JSON object in this exact format:
```json
{
  "document_type": "<type: Aadhaar, PAN, Passport, Driver License, Voter ID, or Other>",
  "id_number": "<extracted ID number or null if not visible>",
  "name_on_document": "<full name as shown or null>",
  "date_of_birth": "<YYYY-MM-DD format or null>",
  "expiry_date": "<YYYY-MM-DD format or null if not applicable>",
  "kyc_passed": <true or false>,
  "confidence": <float between 0 and 1>,
  "tampering_flags": ["<any suspicious indicators>"],
  "validation_notes": "<explanation of validation result>"
}
```

Validation Rules:
- kyc_passed = true if: document is readable, appears authentic, and not expired
- kyc_passed = false if: document is expired, unreadable, or shows tampering signs

Tampering indicators to check:
- Font inconsistencies
- Misaligned text or photos
- Unusual pixelation or artifacts
- Color mismatches
- Overlapping elements
- Missing security features (holograms, watermarks)

If the image is not a KYC document, set kyc_passed to false and note it in validation_notes.
"""


class KYCAgent(BaseAgent):
    """Agent that validates identity documents."""

    def process(
        self,
        image_source: bytes | str | Path,
    ) -> KYCOutput:
        """Validate a KYC document.

        Args:
            image_source: Image bytes, file path, or Path object

        Returns:
            KYCOutput with validation results
        """
        start_time = time.perf_counter()

        try:
            response = self._call_with_retry(
                self._call_vision_llm,
                image_source,
                KYC_PROMPT,
            )

            result = self._parse_json_response(response)
            elapsed = time.perf_counter() - start_time

            # Parse dates
            dob = self._parse_date(result.get("date_of_birth"))
            expiry = self._parse_date(result.get("expiry_date"))

            # Check if expired
            is_expired = False
            if expiry:
                is_expired = expiry < date.today()

            # Override kyc_passed if expired
            kyc_passed = result.get("kyc_passed", False)
            if is_expired:
                kyc_passed = False

            tampering_flags = result.get("tampering_flags", [])
            if is_expired:
                tampering_flags.append("document_expired")

            return KYCOutput(
                kyc_passed=kyc_passed,
                document_type=result.get("document_type"),
                id_number=result.get("id_number"),
                name_on_document=result.get("name_on_document"),
                date_of_birth=dob,
                expiry_date=expiry,
                is_expired=is_expired,
                tampering_flags=tampering_flags,
                confidence=min(max(float(result.get("confidence", 0.5)), 0.0), 1.0),
                processing_time_seconds=elapsed,
            )

        except Exception as e:
            elapsed = time.perf_counter() - start_time
            return KYCOutput(
                kyc_passed=False,
                confidence=0.0,
                tampering_flags=["processing_error"],
                processing_time_seconds=elapsed,
                errors=[str(e)],
            )

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
