"""Claims Agent - extracts structured data using OCR first, then LLM fallback."""

import re
import time
from datetime import date, datetime
from pathlib import Path

from app.models.agent_outputs import ClaimsOutput

from .base import BaseAgent


# Regex patterns for OCR extraction
# Note: OCR often misreads "Rs" as "Ps", "Bs", etc. so we use [A-Z]s pattern
AMOUNT_PATTERNS = [
    # Grand total with currency (handles OCR errors like "Ps" instead of "Rs")
    r"(?:grand\s*total|total\s*amount|net\s*amount|amount\s*payable)[:\s]*(?:[A-Z]s\.?|INR|₹)?\s*([\d,]+(?:\.\d{2})?)",
    # Currency prefix (Rs, Ps for OCR errors, INR, ₹)
    r"(?:Rs\.?|Ps\.?|INR|₹)\s*([\d,]+(?:\.\d{2})?)\s*(?:only|/-)?",
    # Currency suffix
    r"([\d,]+(?:\.\d{2})?)\s*(?:Rs\.?|Ps\.?|INR|₹)",
    # "Rupees X Only" pattern
    r"[Rr]upees\s*([\d,]+(?:\.\d{2})?)\s*[Oo]nly",
]

DATE_PATTERNS = [
    r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
    r"(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})",
]

ICD_PATTERN = r"\b([A-Z]\d{2}(?:\.\d{1,2})?)\b"


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


# Cached EasyOCR reader (singleton)
_ocr_reader = None


def _get_ocr_reader():
    """Get cached OCR reader."""
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        print("  [OCR] Initializing EasyOCR reader (one-time)...")
        # Multi-language support: English, Hindi, Spanish
        _ocr_reader = easyocr.Reader(['en', 'hi', 'es'], gpu=False, verbose=False)
    return _ocr_reader


def extract_amount(text: str) -> float | None:
    """Extract the grand total amount from text.

    Strategy:
    1. First try to find amount after "GRAND TOTAL" specifically
    2. Fall back to largest amount found (usually the total)
    """
    # First, try to extract amount right after "GRAND TOTAL"
    grand_total_pattern = r"grand\s*total[:\s]*(?:[A-Z]s\.?|INR|₹)?\s*([\d,]+(?:\.\d{2})?)"
    grand_match = re.search(grand_total_pattern, text, re.IGNORECASE)
    if grand_match:
        try:
            amount = float(grand_match.group(1).replace(",", ""))
            if amount > 0:
                return amount
        except ValueError:
            pass

    # Fall back to finding all amounts and returning the largest
    amounts = []
    for pattern in AMOUNT_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                # Remove commas and convert to float
                amount = float(match.replace(",", ""))
                if amount > 0:
                    amounts.append(amount)
            except ValueError:
                continue

    # Return the largest amount (usually the grand total)
    return max(amounts) if amounts else None


def extract_dates(text: str) -> list[date]:
    """Extract dates from text."""
    dates = []

    for pattern in DATE_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            for fmt in ["%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y",
                        "%d %b %Y", "%d %B %Y", "%d %b %y"]:
                try:
                    d = datetime.strptime(match, fmt).date()
                    dates.append(d)
                    break
                except ValueError:
                    continue

    return dates


def extract_icd_codes(text: str) -> list[str]:
    """Extract ICD-10 codes from text."""
    matches = re.findall(ICD_PATTERN, text.upper())
    # Filter out likely false positives
    valid_codes = [m for m in matches if len(m) >= 3]
    return list(set(valid_codes))


def extract_provider_name(text: str) -> str | None:
    """Try to extract hospital/provider name."""
    patterns = [
        r"([\w\s]+(?:hospital|clinic|medical|healthcare|diagnostics)[\w\s]*)",
        r"^([A-Z][\w\s]{5,50})(?:pvt|private|ltd|limited)?",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            name = match.group(1).strip()
            if len(name) > 3:
                return name[:100]  # Limit length

    return None


def extract_with_ocr(image_path: Path) -> dict | None:
    """Extract claim data using OCR.

    Returns dict with extracted fields or None if OCR fails.
    """
    try:
        reader = _get_ocr_reader()
        results = reader.readtext(str(image_path))
        text = " ".join([r[1] for r in results])

        if not text.strip():
            return None

        # Extract fields
        amount = extract_amount(text)
        dates = extract_dates(text)
        icd_codes = extract_icd_codes(text)
        provider = extract_provider_name(text)

        return {
            "claim_amount": amount,
            "service_date": dates[0] if dates else None,
            "icd_10_codes": icd_codes,
            "provider_name": provider,
            "raw_text": text,
        }

    except ImportError:
        print("  [Claims] EasyOCR not installed, skipping OCR")
        return None
    except Exception as e:
        print(f"  [Claims] OCR error: {e}")
        return None


# Document types that don't require claim_amount
NON_BILLING_DOCS = ["Prescriptions", "Medical Reports"]


class ClaimsAgent(BaseAgent):
    """Agent that extracts claim data using OCR first, then LLM fallback."""

    def process(
        self,
        image_source: bytes | str | Path,
        doc_type=None,
    ) -> ClaimsOutput:
        """Extract claim data from a document.

        Strategy:
        1. OCR + regex extraction (fast, no API call)
        2. Vision LLM (fallback if amount not found)

        Args:
            image_source: Image bytes, file path, or Path object
            doc_type: Document type (to determine if amount is required)

        Returns:
            ClaimsOutput with extracted fields
        """
        start_time = time.perf_counter()

        # Check if this is a non-billing document (amount not required)
        doc_type_str = doc_type.value if doc_type else None
        is_non_billing = doc_type_str in NON_BILLING_DOCS

        # Get image path
        image_path = None
        if isinstance(image_source, (str, Path)):
            image_path = Path(image_source)

        # Step 1: Try OCR extraction
        if image_path and image_path.exists():
            extracted = extract_with_ocr(image_path)

            # For billing docs, require amount; for prescriptions/reports, amount is optional
            has_amount = extracted and extracted.get("claim_amount")

            if has_amount or (is_non_billing and extracted):
                elapsed = time.perf_counter() - start_time
                amount = extracted.get("claim_amount") if extracted else None
                print(f"  [Claims] Extracted by OCR: amount={amount}, non_billing={is_non_billing}")

                # Note: Don't include CPT codes from OCR - too error-prone
                return ClaimsOutput(
                    claim_amount=amount,
                    currency="INR",
                    icd_10_codes=extracted.get("icd_10_codes", []) if extracted else [],
                    cpt_codes=[],  # Skip CPT from OCR - unreliable
                    provider_name=extracted.get("provider_name") if extracted else None,
                    service_date=extracted.get("service_date") if extracted else None,
                    schema_valid=True,  # Valid for non-billing even without amount
                    validation_errors=[],
                    confidence=0.75 if has_amount else 0.7,
                    processing_time_seconds=elapsed,
                )

        # Step 2: Fall back to Vision LLM
        print(f"  [Claims] Falling back to LLM: {self.model_name}")
        return self._extract_with_llm(image_source, start_time, is_non_billing)

    def _extract_with_llm(
        self,
        image_source: bytes | str | Path,
        start_time: float,
        is_non_billing: bool = False,
    ) -> ClaimsOutput:
        """Extract claim data using vision LLM (fallback method)."""
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

            # Validate schema
            # For prescriptions/medical reports, claim_amount is NOT required
            validation_errors = []
            schema_valid = True

            if claim_amount is None and not is_non_billing:
                validation_errors.append("claim_amount not found")
                schema_valid = False

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
            print(f"  [Claims] Result: amount={claim_amount}, valid={schema_valid}")
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
        valid_codes = []
        pattern = re.compile(r"^[A-Z]\d{2}\.?\d*$", re.IGNORECASE)

        for code in codes or []:
            code_str = str(code).strip().upper()
            if pattern.match(code_str):
                valid_codes.append(code_str)

        return valid_codes

    def _validate_cpt_codes(self, codes: list) -> list[str]:
        """Validate and clean CPT codes."""
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
