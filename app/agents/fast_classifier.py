"""Fast Classifier - uses filename patterns and OCR before falling back to LLM."""

import re
import time
from pathlib import Path

from app.config import get_settings
from app.models.agent_outputs import ClassifierOutput
from app.models.document import DocType


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
}


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
        _ocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
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
        print("  [FastClassifier] EasyOCR not installed, skipping OCR")
        return None, 0.0, ""
    except Exception as e:
        print(f"  [FastClassifier] OCR error: {e}")
        return None, 0.0, ""


class FastClassifierAgent:
    """Fast classifier that uses filename/OCR before LLM fallback."""

    def __init__(self):
        self.settings = get_settings()
        self._llm_classifier = None  # Lazy load

    def process(self, image_source: bytes | str | Path) -> ClassifierOutput:
        """Classify document using fastest available method.

        Order:
        1. Filename pattern matching
        2. OCR + keyword matching
        3. LLM (fallback)
        """
        start_time = time.perf_counter()

        # Get filename if path provided
        filename = ""
        image_path = None
        if isinstance(image_source, (str, Path)):
            image_path = Path(image_source)
            filename = image_path.name

        # Step 1: Try filename pattern
        if filename:
            doc_type, confidence = classify_by_filename(filename)
            if doc_type:
                elapsed = time.perf_counter() - start_time
                print(f"  [FastClassifier] Classified by filename: {doc_type.value} ({confidence:.0%})")
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
                print(f"  [FastClassifier] Classified by OCR: {doc_type.value} ({confidence:.0%})")
                return ClassifierOutput(
                    doc_type=doc_type,
                    confidence=confidence,
                    routing_tags=["ocr_match", f"queue:{self._get_queue(doc_type)}"],
                    processing_time_seconds=elapsed,
                )

        # Step 3: Fall back to LLM
        print(f"  [FastClassifier] Falling back to LLM...")
        if self._llm_classifier is None:
            from app.agents.classifier import ClassifierAgent
            self._llm_classifier = ClassifierAgent()

        return self._llm_classifier.process(image_source)

    def _get_queue(self, doc_type: DocType) -> str:
        """Get queue name for document type."""
        return self.settings.queue_routing.get(doc_type.value, "manual_review_queue")
