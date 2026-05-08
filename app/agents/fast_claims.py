"""Fast Claims Extractor - uses OCR + regex before falling back to LLM."""

import re
import time
from datetime import date, datetime
from pathlib import Path

from app.models.agent_outputs import ClaimsOutput


# Regex patterns for extraction
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
CPT_PATTERN = r"\b(\d{5})\b"


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


def extract_cpt_codes(text: str) -> list[str]:
    """Extract CPT codes from text."""
    matches = re.findall(CPT_PATTERN, text)
    # CPT codes are typically in 90000-99999 range for E/M, etc.
    valid_codes = [m for m in matches if 10000 <= int(m) <= 99999]
    return list(set(valid_codes))


def extract_provider_name(text: str) -> str | None:
    """Try to extract hospital/provider name."""
    # Look for common patterns
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


# Cached EasyOCR reader (singleton)
_ocr_reader = None


def _get_ocr_reader():
    """Get cached OCR reader."""
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        print("  [OCR] Initializing EasyOCR reader (one-time)...")
        _ocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    return _ocr_reader


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
        cpt_codes = extract_cpt_codes(text)
        provider = extract_provider_name(text)

        return {
            "claim_amount": amount,
            "service_date": dates[0] if dates else None,
            "icd_10_codes": icd_codes,
            "cpt_codes": cpt_codes,
            "provider_name": provider,
            "raw_text": text,
        }

    except ImportError:
        print("  [FastClaims] EasyOCR not installed, skipping OCR")
        return None
    except Exception as e:
        print(f"  [FastClaims] OCR error: {e}")
        return None


class FastClaimsAgent:
    """Fast claims extractor using OCR + regex before LLM fallback."""

    def __init__(self):
        self._llm_claims = None  # Lazy load

    def process(self, image_source: bytes | str | Path) -> ClaimsOutput:
        """Extract claims data using fastest available method.

        Order:
        1. OCR + regex extraction
        2. LLM (fallback if amount not found)
        """
        start_time = time.perf_counter()

        # Get image path
        image_path = None
        if isinstance(image_source, (str, Path)):
            image_path = Path(image_source)

        # Step 1: Try OCR extraction
        if image_path and image_path.exists():
            extracted = extract_with_ocr(image_path)

            if extracted and extracted.get("claim_amount"):
                elapsed = time.perf_counter() - start_time
                print(f"  [FastClaims] Extracted by OCR: amount={extracted['claim_amount']}")

                # Note: Don't include CPT codes from OCR - too error-prone
                # (amounts like 34531 get falsely detected as CPT codes)
                return ClaimsOutput(
                    claim_amount=extracted["claim_amount"],
                    currency="INR",
                    icd_10_codes=extracted.get("icd_10_codes", []),
                    cpt_codes=[],  # Skip CPT from OCR - unreliable for bills
                    provider_name=extracted.get("provider_name"),
                    service_date=extracted.get("service_date"),
                    schema_valid=True,
                    validation_errors=[],
                    confidence=0.75,  # Lower confidence for OCR extraction
                    processing_time_seconds=elapsed,
                )

        # Step 2: Fall back to LLM
        print(f"  [FastClaims] Falling back to LLM...")
        if self._llm_claims is None:
            from app.agents.claims import ClaimsAgent
            self._llm_claims = ClaimsAgent()

        return self._llm_claims.process(image_source)
