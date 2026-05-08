#!/usr/bin/env python
"""Test script to verify the policy document flow."""

import warnings
import os

os.environ["PYTHONWARNINGS"] = "ignore"
warnings.filterwarnings("ignore")

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agents.policy import PolicyAgent
from app.rag.retriever import PolicyRetriever
from app.models.agent_outputs import ClaimsOutput


def test_policy_flow():
    print("=" * 60)
    print("  Policy Document Flow Test")
    print("=" * 60)

    # Step 1: Index policies
    print("\n[Step 1] Indexing policy documents...")
    policy_agent = PolicyAgent()
    count = policy_agent.index_policies()
    print(f"  Indexed {count} chunks from policy PDFs")

    # Step 2: Check retriever
    print("\n[Step 2] Verifying ChromaDB collection...")
    retriever = PolicyRetriever()
    collection_count = retriever.get_collection_count()
    print(f"  Collection contains {collection_count} documents")

    # Step 3: Test retrieval with sample queries
    print("\n[Step 3] Testing policy retrieval...")

    test_queries = [
        {
            "name": "Cardiac condition",
            "icd_codes": ["I21.9"],  # Myocardial infarction
            "cpt_codes": ["93000"],  # ECG
            "diagnosis": "Acute myocardial infarction",
        },
        {
            "name": "Respiratory condition",
            "icd_codes": ["J18.9"],  # Pneumonia
            "cpt_codes": ["99223"],  # Hospital admission
            "diagnosis": "Community-acquired pneumonia",
        },
        {
            "name": "Cosmetic procedure (should be excluded)",
            "icd_codes": [],
            "cpt_codes": ["15830"],  # Cosmetic surgery
            "diagnosis": "Rhinoplasty for aesthetic purposes",
        },
        {
            "name": "Orthopedic fracture",
            "icd_codes": ["S72.001"],  # Hip fracture
            "cpt_codes": ["27236"],  # Open treatment hip fracture
            "diagnosis": "Fracture of neck of femur",
        },
    ]

    for query in test_queries:
        print(f"\n  Testing: {query['name']}")
        clauses = retriever.retrieve_for_codes(
            icd_codes=query["icd_codes"],
            cpt_codes=query["cpt_codes"],
            diagnosis=query["diagnosis"],
            n_results=2,
        )
        print(f"    Found {len(clauses)} relevant clauses:")
        for i, clause in enumerate(clauses[:2], 1):
            section = clause.section or "Unknown section"
            text_preview = clause.text[:100].replace("\n", " ") + "..."
            print(f"    [{i}] {section}: {text_preview}")
            print(f"        Relevance: {clause.relevance_score:.2f}")

    # Step 4: Test full policy agent processing
    print("\n[Step 4] Testing full policy agent processing...")

    # Create a mock claims output
    claims_output = ClaimsOutput(
        claim_amount=45000.0,
        currency="INR",
        icd_10_codes=["I21.9"],  # Heart attack
        cpt_codes=["93000", "99223"],
        provider_name="City Heart Hospital",
        service_date=None,
        schema_valid=True,
        validation_errors=[],
        confidence=0.9,
        processing_time_seconds=0.0,
    )

    print(f"  Mock claim: Heart attack treatment, Rs. 45,000")
    result = policy_agent.process(claims_output=claims_output)

    print(f"\n  Policy Agent Result:")
    print(f"    Covered: {result.covered}")
    print(f"    Coverage %: {result.coverage_percentage}")
    print(f"    Confidence: {result.confidence:.2f}")
    print(f"    Exclusions: {result.exclusions}")
    print(f"    Matching clauses: {len(result.matching_clauses)}")

    # Step 5: Test with excluded procedure
    print("\n[Step 5] Testing with excluded procedure (cosmetic)...")

    cosmetic_claim = ClaimsOutput(
        claim_amount=150000.0,
        currency="INR",
        icd_10_codes=[],
        cpt_codes=["15830"],  # Cosmetic
        provider_name="Cosmetic Surgery Center",
        diagnosis="Rhinoplasty for aesthetic enhancement",
        service_date=None,
        schema_valid=True,
        validation_errors=[],
        confidence=0.9,
        processing_time_seconds=0.0,
    )

    print(f"  Mock claim: Cosmetic rhinoplasty, Rs. 1,50,000")
    result = policy_agent.process(claims_output=cosmetic_claim)

    print(f"\n  Policy Agent Result:")
    print(f"    Covered: {result.covered}")
    print(f"    Coverage %: {result.coverage_percentage}")
    print(f"    Confidence: {result.confidence:.2f}")
    print(f"    Exclusions: {result.exclusions}")

    print("\n" + "=" * 60)
    print("  Policy Flow Test Complete!")
    print("=" * 60)


if __name__ == "__main__":
    test_policy_flow()
