"""Classifier Agent - identifies document types using regex, OCR, then LLM fallback."""

import re
import time
from pathlib import Path

from app.config import get_settings
from app.models.agent_outputs import ClassifierOutput
from app.models.document import DocType

from .base import BaseAgent


# Filename patterns for quick classification
FILENAME_PATTERNS = {
    DocType.PATIENT_BILL: [
        r"bill[_\-]",
        r"invoice[_\-]",
        r"billing",
        r"receipt",
    ],
    DocType.CLAIM_FORM: [
        r"claim[_\-]",
        r"claim_form",
    ],
    DocType.KYC_DOCUMENT: [
        r"kyc[_\-]",
        r"aadhaar",
        r"aadhar",
        r"pan[_\-]",
        r"passport",
        r"voter",
        r"driving[_\-]?license",
    ],
    DocType.MEDICAL_REPORT: [
        r"report[_\-]",
        r"lab[_\-]",
        r"diagnostic",
        r"pathology",
        r"radiology",
        r"xray",
        r"mri",
        r"ct[_\-]?scan",
    ],
    DocType.PRESCRIPTION: [
        r"prescription",
        r"rx[_\-]",
    ],
    DocType.POLICY_DOCUMENT: [
        r"policy[_\-]",
        r"insurance[_\-]?policy",
        r"coverage",
        r"terms[_\-]?and[_\-]?conditions",
        r"plan[_\-]?document",
    ],
}

# OCR text patterns for classification
OCR_KEYWORDS = {
    DocType.PATIENT_BILL: [
        "tax invoice", "hospital billing", "billing statement",
        "invoice no", "bill no", "grand total", "total amount",
        "cgst", "sgst", "gst", "room charges",
    ],
    DocType.CLAIM_FORM: [
        "claim form", "insurance claim", "claim submission",
        "policyholder", "policy number", "sum insured",
    ],
    DocType.KYC_DOCUMENT: [
        "aadhaar", "aadhar", "uidai", "permanent account number",
        "income tax department", "passport", "republic of india",
        "voter id", "election commission", "driving licence",
    ],
    DocType.MEDICAL_REPORT: [
        "laboratory report", "test report", "diagnostic report",
        "pathology", "radiology", "blood test", "urine test",
        "reference range", "normal range", "findings",
    ],
    DocType.PRESCRIPTION: [
        "prescription", "rx", "medicine", "tablet", "capsule",
        "dosage", "times a day", "after food", "before food",
    ],
    DocType.POLICY_DOCUMENT: [
        "insurance policy", "terms and conditions", "coverage details",
        "policy document", "sum insured", "exclusions", "waiting period",
        "pre-existing", "network hospital", "cashless", "reimbursement",
        "premium", "deductible", "co-pay", "policy period",
    ],
}


CLASSIFICATION_PROMPT = """You are an intelligent document classifier for MediShield Insurance.

Examine the scanned document image carefully — consider its layout, visible text, headings, tables, stamps, logos, and any other visual cues.

Classify the document into EXACTLY ONE of the following categories:
  - Patient Bills
  - Claim Forms
  - KYC Documents
  - Medical Reports
  - Prescriptions
  - Policy Documents
  - Unknown

Category definitions:
- Patient Bills: Hospital or pharmacy invoices showing charges, itemised costs, or payment receipts.
- Claim Forms: Insurance claim submission forms with patient and treatment details.
- KYC Documents: Government-issued identity proofs such as Aadhaar card, PAN card, passport, or driver's license.
- Medical Reports: Lab results, diagnostic imaging reports, blood work, pathology reports, or discharge summaries.
- Prescriptions: Doctor-issued medication prescriptions listing drugs and dosages.
- Policy Documents: Insurance policy PDFs containing terms, conditions, coverage details, exclusions, and benefits.
- Unknown: Anything that does not clearly fit one of the above categories.

Respond with a JSON object in this exact format:
```json
{
  "doc_type": "<category name exactly as listed above>",
  "confidence": <float between 0 and 1>,
  "routing_tags": ["<relevant tag1>", "<relevant tag2>"],
  "reasoning": "<brief explanation of classification>"
}
```

Rules:
1. The doc_type must be one of the exact category names listed above.
2. Confidence should reflect how certain you are (1.0 = absolutely certain, 0.5 = uncertain).
3. Routing tags should include relevant keywords (e.g., "urgent", "high_value", "verification_needed").
4. If you are uncertain, set confidence below 0.6 and use "Unknown" if truly unclear.
"""


def classify_by_filename(filename: str) -> tuple[DocType | None, float]:
    """Try to classify document by filename pattern.

    Returns:
        Tuple of (DocType or None, confidence)
    """
    filename_lower = filename.lower()

    for doc_type, patterns in FILENAME_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, filename_lower, re.IGNORECASE):
                return doc_type, 0.9  # High confidence for filename match

    return None, 0.0


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


def classify_by_ocr(image_path: Path) -> tuple[DocType | None, float, str]:
    """Try to classify document using OCR text extraction.

    Returns:
        Tuple of (DocType or None, confidence, extracted_text)
    """
    try:
        reader = _get_ocr_reader()
        results = reader.readtext(str(image_path))
        text = " ".join([r[1] for r in results]).lower()

        if not text.strip():
            return None, 0.0, ""

        # Check for keywords
        best_match = None
        best_score = 0

        for doc_type, keywords in OCR_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > best_score:
                best_score = score
                best_match = doc_type

        if best_match and best_score >= 2:  # At least 2 keyword matches
            confidence = min(0.85, 0.5 + (best_score * 0.1))
            return best_match, confidence, text

        return None, 0.0, text

    except ImportError:
        print("  [Classifier] EasyOCR not installed, skipping OCR")
        return None, 0.0, ""
    except Exception as e:
        print(f"  [Classifier] OCR error: {e}")
        return None, 0.0, ""


class ClassifierAgent(BaseAgent):
    """Agent that classifies documents using regex, OCR, then LLM fallback."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.settings = get_settings()

    def process(
        self,
        image_source: bytes | str | Path,
    ) -> ClassifierOutput:
        """Classify a document image.

        Strategy:
        1. Filename pattern matching (instant, no API call)
        2. OCR + keyword matching (fast, no API call)
        3. Vision LLM (fallback, accurate but slower)

        Args:
            image_source: Image bytes, file path, or Path object

        Returns:
            ClassifierOutput with doc_type, confidence, and routing_tags
        """
        start_time = time.perf_counter()

        # Get filename if path provided
        filename = ""
        image_path = None
        if isinstance(image_source, (str, Path)):
            image_path = Path(image_source)
            filename = image_path.name

        # Step 1: Try filename pattern matching
        if filename:
            doc_type, confidence = classify_by_filename(filename)
            if doc_type:
                elapsed = time.perf_counter() - start_time
                print(f"  [Classifier] Classified by filename: {doc_type.value} ({confidence:.0%})")
                return ClassifierOutput(
                    doc_type=doc_type,
                    confidence=confidence,
                    routing_tags=["filename_match", f"queue:{self._get_queue(doc_type)}"],
                    processing_time_seconds=elapsed,
                )

        # Step 2: Try OCR classification
        if image_path and image_path.exists():
            doc_type, confidence, ocr_text = classify_by_ocr(image_path)
            if doc_type:
                elapsed = time.perf_counter() - start_time
                print(f"  [Classifier] Classified by OCR: {doc_type.value} ({confidence:.0%})")
                return ClassifierOutput(
                    doc_type=doc_type,
                    confidence=confidence,
                    routing_tags=["ocr_match", f"queue:{self._get_queue(doc_type)}"],
                    processing_time_seconds=elapsed,
                )

        # Step 3: Fall back to Vision LLM
        print(f"  [Classifier] Falling back to LLM: {self.model_name}")
        return self._classify_with_llm(image_source, start_time)

    def _classify_with_llm(
        self,
        image_source: bytes | str | Path,
        start_time: float,
    ) -> ClassifierOutput:
        """Classify using vision LLM (fallback method)."""
        try:
            response = self._call_with_retry(
                self._call_vision_llm,
                image_source,
                CLASSIFICATION_PROMPT,
            )
            print(f"  [Classifier] LLM response: {response[:150]}...")

            result = self._parse_json_response(response)
            elapsed = time.perf_counter() - start_time

            doc_type = DocType.from_string(result.get("doc_type", "Unknown"))
            confidence = float(result.get("confidence", 0.5))
            routing_tags = result.get("routing_tags", [])

            # Add queue routing tag
            queue = self._get_queue(doc_type)
            if f"queue:{queue}" not in routing_tags:
                routing_tags.append(f"queue:{queue}")

            return ClassifierOutput(
                doc_type=doc_type,
                confidence=min(max(confidence, 0.0), 1.0),
                routing_tags=routing_tags,
                processing_time_seconds=elapsed,
            )

        except Exception as e:
            elapsed = time.perf_counter() - start_time
            print(f"  [Classifier] ERROR: {type(e).__name__}: {e}")
            return ClassifierOutput(
                doc_type=DocType.UNKNOWN,
                confidence=0.0,
                routing_tags=["error", "manual_review"],
                processing_time_seconds=elapsed,
                errors=[str(e)],
            )

    def _get_queue(self, doc_type: DocType) -> str:
        """Get queue name for document type."""
        return self.settings.queue_routing.get(doc_type.value, "manual_review_queue")
