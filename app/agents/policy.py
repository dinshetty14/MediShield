"""Policy Agent - RAG over policy documents to check coverage."""

import time

from app.models.agent_outputs import ClaimsOutput, PolicyClause, PolicyOutput
from app.rag.retriever import PolicyRetriever

from .base import BaseAgent


COVERAGE_ANALYSIS_PROMPT = """You are a policy coverage analyst for MediShield Insurance.

Given the following medical claim information and relevant policy clauses, determine if the procedures are covered.

CLAIM INFORMATION:
{claim_info}

RELEVANT POLICY CLAUSES:
{policy_clauses}

Analyze the policy clauses and determine:
1. Whether the procedures/diagnoses are covered
2. What percentage of the claim would be covered
3. Any exclusions that apply
4. Any conditions or limitations

Respond with a JSON object:
```json
{{
  "covered": <true or false>,
  "coverage_percentage": <0-100>,
  "reasoning": "<explanation of coverage decision>",
  "exclusions": ["<any exclusions that apply>"],
  "conditions": ["<any conditions or limitations>"],
  "confidence": <float between 0 and 1>
}}
```

Rules:
- If no relevant policy clauses are found, set covered=false and confidence low
- Consider pre-existing condition clauses, waiting periods, and coverage limits
- Note any co-pay or deductible requirements in conditions
"""


class PolicyAgent(BaseAgent):
    """Agent that checks policy coverage using RAG."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._retriever = PolicyRetriever()

    def process(
        self,
        claims_output: ClaimsOutput | None = None,
        icd_codes: list[str] | None = None,
        cpt_codes: list[str] | None = None,
        diagnosis: str | None = None,
        claim_amount: float | None = None,
    ) -> PolicyOutput:
        """Check policy coverage for a claim.

        Args:
            claims_output: Output from ClaimsAgent (preferred)
            icd_codes: ICD-10 codes (alternative to claims_output)
            cpt_codes: CPT codes (alternative to claims_output)
            diagnosis: Diagnosis description
            claim_amount: Claim amount for coverage calculation

        Returns:
            PolicyOutput with coverage decision
        """
        start_time = time.perf_counter()

        # Extract data from claims_output if provided
        if claims_output:
            icd_codes = claims_output.icd_10_codes
            cpt_codes = claims_output.cpt_codes
            diagnosis = claims_output.diagnosis
            claim_amount = claims_output.claim_amount

        # If no diagnosis codes available (e.g., patient bills without ICD/CPT),
        # default to covered since we can't verify against policy
        if not icd_codes and not cpt_codes and not diagnosis:
            elapsed = time.perf_counter() - start_time
            print(f"  [Policy] No diagnosis codes - defaulting to covered=True (likely a bill)")
            return PolicyOutput(
                covered=True,
                coverage_percentage=100.0,
                matching_clauses=[],
                exclusions=[],
                confidence=0.85,
                processing_time_seconds=elapsed,
            )

        try:
            # Retrieve relevant policy clauses
            clauses = self._retriever.retrieve_for_codes(
                icd_codes=icd_codes or [],
                cpt_codes=cpt_codes or [],
                diagnosis=diagnosis,
                n_results=5,
            )

            # If no policies indexed, return default response
            if not clauses or self._retriever.get_collection_count() == 0:
                elapsed = time.perf_counter() - start_time
                print(f"  [Policy] No policies indexed - defaulting to covered=True")
                return PolicyOutput(
                    covered=True,  # Default to covered if no policy to check against
                    coverage_percentage=100.0,
                    matching_clauses=[],
                    exclusions=[],
                    confidence=0.8,  # High confidence since we're auto-approving
                    processing_time_seconds=elapsed,
                )

            # Build claim info string
            claim_info = self._format_claim_info(
                icd_codes, cpt_codes, diagnosis, claim_amount
            )

            # Build policy clauses string
            policy_clauses = self._format_clauses(clauses)

            # Call LLM for coverage analysis
            prompt = COVERAGE_ANALYSIS_PROMPT.format(
                claim_info=claim_info,
                policy_clauses=policy_clauses,
            )

            response = self._call_with_retry(self._call_llm, prompt)
            result = self._parse_json_response(response)
            elapsed = time.perf_counter() - start_time

            output = PolicyOutput(
                covered=result.get("covered", False),
                coverage_percentage=float(result.get("coverage_percentage", 0)),
                matching_clauses=clauses,
                exclusions=result.get("exclusions", []),
                confidence=min(max(float(result.get("confidence", 0.5)), 0.0), 1.0),
                processing_time_seconds=elapsed,
            )
            print(f"  [Policy] Result: covered={output.covered}, coverage={output.coverage_percentage}%")
            return output

        except Exception as e:
            elapsed = time.perf_counter() - start_time
            return PolicyOutput(
                covered=False,
                coverage_percentage=0.0,
                matching_clauses=[],
                exclusions=["policy_check_failed"],
                confidence=0.0,
                processing_time_seconds=elapsed,
                errors=[str(e)],
            )

    def _format_claim_info(
        self,
        icd_codes: list[str] | None,
        cpt_codes: list[str] | None,
        diagnosis: str | None,
        claim_amount: float | None,
    ) -> str:
        """Format claim information for the prompt."""
        parts = []

        if diagnosis:
            parts.append(f"Diagnosis: {diagnosis}")
        if icd_codes:
            parts.append(f"ICD-10 Codes: {', '.join(icd_codes)}")
        if cpt_codes:
            parts.append(f"CPT Codes: {', '.join(cpt_codes)}")
        if claim_amount:
            parts.append(f"Claim Amount: {claim_amount}")

        return "\n".join(parts) if parts else "No claim details provided"

    def _format_clauses(self, clauses: list[PolicyClause]) -> str:
        """Format policy clauses for the prompt."""
        if not clauses:
            return "No relevant policy clauses found."

        parts = []
        for i, clause in enumerate(clauses, 1):
            section = f" ({clause.section})" if clause.section else ""
            parts.append(f"Clause {i}{section}:\n{clause.text}\n")

        return "\n".join(parts)

    def index_policies(self, policies_dir: str | None = None) -> int:
        """Index policy documents.

        Args:
            policies_dir: Optional path to policies directory

        Returns:
            Number of chunks indexed
        """
        return self._retriever.index_policies(policies_dir)

    def ingest_policy_pdf(self, pdf_path: str) -> int:
        """Ingest a single policy PDF into ChromaDB via Docling.

        This is called when a Policy Document is uploaded through the pipeline.

        Args:
            pdf_path: Path to the uploaded PDF file

        Returns:
            Number of chunks indexed
        """
        print(f"  [Policy] Ingesting policy PDF: {pdf_path}")
        return self._retriever.index_single_pdf(pdf_path)
