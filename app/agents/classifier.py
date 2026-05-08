"""Classifier Agent - identifies document types using vision LLM."""

import time
from pathlib import Path

from app.config import get_settings
from app.models.agent_outputs import ClassifierOutput
from app.models.document import DocType

from .base import BaseAgent


CLASSIFICATION_PROMPT = """You are an intelligent document classifier for MediShield Insurance.

Examine the scanned document image carefully — consider its layout, visible text, headings, tables, stamps, logos, and any other visual cues.

Classify the document into EXACTLY ONE of the following categories:
  - Patient Bills
  - Claim Forms
  - KYC Documents
  - Medical Reports
  - Prescriptions
  - Unknown

Category definitions:
- Patient Bills: Hospital or pharmacy invoices showing charges, itemised costs, or payment receipts.
- Claim Forms: Insurance claim submission forms with patient and treatment details.
- KYC Documents: Government-issued identity proofs such as Aadhaar card, PAN card, passport, or driver's license.
- Medical Reports: Lab results, diagnostic imaging reports, blood work, pathology reports, or discharge summaries.
- Prescriptions: Doctor-issued medication prescriptions listing drugs and dosages.
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


class ClassifierAgent(BaseAgent):
    """Agent that classifies documents into predefined categories."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.settings = get_settings()

    def process(
        self,
        image_source: bytes | str | Path,
    ) -> ClassifierOutput:
        """Classify a document image.

        Args:
            image_source: Image bytes, file path, or Path object

        Returns:
            ClassifierOutput with doc_type, confidence, and routing_tags
        """
        start_time = time.perf_counter()

        try:
            print(f"  [Classifier] Calling vision LLM: {self.model_name}")
            response = self._call_with_retry(
                self._call_vision_llm,
                image_source,
                CLASSIFICATION_PROMPT,
            )
            print(f"  [Classifier] Got response: {response[:200]}...")

            result = self._parse_json_response(response)
            print(f"  [Classifier] Parsed result: {result}")
            elapsed = time.perf_counter() - start_time

            doc_type = DocType.from_string(result.get("doc_type", "Unknown"))
            confidence = float(result.get("confidence", 0.5))
            routing_tags = result.get("routing_tags", [])

            # Add queue routing tag
            queue = self.settings.queue_routing.get(doc_type.value, "manual_review_queue")
            if queue not in routing_tags:
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
