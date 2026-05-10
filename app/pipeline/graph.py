"""LangGraph pipeline for document processing with conditional routing."""

import time
from pathlib import Path
from typing import Literal

from langgraph.graph import END, StateGraph

from app.agents.claims import ClaimsAgent
from app.agents.classifier import ClassifierAgent
from app.agents.fraud import FraudAgent
from app.agents.kyc import KYCAgent
from app.agents.orchestrator import OrchestratorAgent
from app.agents.policy import PolicyAgent
from app.models.agent_outputs import PolicyIngestionOutput
from app.models.document import DocType

from .state import PipelineState


# Initialize agents
_classifier = ClassifierAgent()
_kyc = KYCAgent()
_claims = ClaimsAgent()
_policy = PolicyAgent()
_fraud = FraudAgent()
_orchestrator = OrchestratorAgent()


def classifier_node(state: PipelineState) -> PipelineState:
    """Classify the document type."""
    image_source = state.get("image_bytes") or state.get("image_path")
    if not image_source:
        return {
            "error": "No image provided",
            "current_step": "classifier",
        }

    output = _classifier.process(image_source)
    return {
        "classifier_output": output,
        "doc_type": output.doc_type,
        "current_step": "classified",
    }


def kyc_node(state: PipelineState) -> PipelineState:
    """Validate KYC documents."""
    image_source = state.get("image_bytes") or state.get("image_path")
    output = _kyc.process(image_source)
    return {
        "kyc_output": output,
        "current_step": "kyc_complete",
    }


def policy_ingestion_node(state: PipelineState) -> PipelineState:
    """Ingest policy PDF into ChromaDB via Docling.

    This node handles Policy Document uploads - it extracts text,
    chunks it, and stores in the vector database for RAG retrieval.
    """
    image_path = state.get("image_path")
    start_time = time.perf_counter()

    if not image_path:
        return {
            "policy_ingestion_output": PolicyIngestionOutput(
                chunks_indexed=0,
                ingestion_successful=False,
                confidence=0.0,
                errors=["No file path provided for policy ingestion"],
            ),
            "current_step": "policy_ingestion_failed",
        }

    pdf_path = Path(image_path)

    # Check if it's a PDF
    if pdf_path.suffix.lower() != ".pdf":
        return {
            "policy_ingestion_output": PolicyIngestionOutput(
                chunks_indexed=0,
                ingestion_successful=False,
                confidence=0.0,
                errors=[f"Policy documents must be PDFs, got: {pdf_path.suffix}"],
            ),
            "current_step": "policy_ingestion_failed",
        }

    try:
        print(f"  [Pipeline] Ingesting policy PDF: {pdf_path.name}")
        chunks_indexed = _policy.ingest_policy_pdf(str(pdf_path))
        elapsed = time.perf_counter() - start_time

        return {
            "policy_ingestion_output": PolicyIngestionOutput(
                chunks_indexed=chunks_indexed,
                policy_name=pdf_path.stem,
                ingestion_successful=True,
                confidence=1.0 if chunks_indexed > 0 else 0.5,
                processing_time_seconds=elapsed,
            ),
            "current_step": "policy_ingestion_complete",
        }
    except Exception as e:
        elapsed = time.perf_counter() - start_time
        print(f"  [Pipeline] Policy ingestion error: {e}")
        return {
            "policy_ingestion_output": PolicyIngestionOutput(
                chunks_indexed=0,
                ingestion_successful=False,
                confidence=0.0,
                processing_time_seconds=elapsed,
                errors=[str(e)],
            ),
            "current_step": "policy_ingestion_failed",
        }


def extraction_node(state: PipelineState) -> PipelineState:
    """Run Claims and Policy extraction sequentially.

    Claims Agent extracts amounts, codes, etc.
    Policy Agent checks coverage based on claims output.

    Note: Policy depends on Claims output, so they run sequentially.
    """
    doc_type = state.get("doc_type")
    image_source = state.get("image_bytes") or state.get("image_path")

    # Step 1: Claims extraction
    print("  [Pipeline] Running Claims Agent...")
    claims_output = _claims.process(image_source, doc_type=doc_type)

    # Step 2: Policy check (depends on claims output)
    print("  [Pipeline] Running Policy Agent...")
    policy_output = _policy.process(claims_output=claims_output)

    return {
        "claims_output": claims_output,
        "policy_output": policy_output,
        "current_step": "extraction_complete",
    }


def fraud_node(state: PipelineState) -> PipelineState:
    """Check for fraud indicators."""
    claims_output = state.get("claims_output")
    output = _fraud.process(claims_output=claims_output)
    return {
        "fraud_output": output,
        "current_step": "fraud_complete",
    }


def orchestrator_node(state: PipelineState) -> PipelineState:
    """Make final decision."""
    output = _orchestrator.process(
        classifier_output=state.get("classifier_output"),
        kyc_output=state.get("kyc_output"),
        claims_output=state.get("claims_output"),
        policy_output=state.get("policy_output"),
        fraud_output=state.get("fraud_output"),
    )
    return {
        "final_decision": output,
        "current_step": "decided",
    }


def route_by_doc_type(state: PipelineState) -> Literal["kyc", "extraction", "policy_ingestion", "orchestrator"]:
    """Route to appropriate agents based on document type.

    Routing logic:
    - KYC documents → KYC Agent → Fraud → Orchestrator
    - Policy documents → Policy Ingestion (Docling + ChromaDB) → END
    - Unknown documents → Orchestrator (skip all processing)
    - All other documents → Claims → Policy → Fraud → Orchestrator
    """
    doc_type = state.get("doc_type")

    if doc_type == DocType.KYC_DOCUMENT:
        return "kyc"
    elif doc_type == DocType.POLICY_DOCUMENT:
        return "policy_ingestion"
    elif doc_type == DocType.UNKNOWN:
        return "orchestrator"
    else:
        return "extraction"


def build_pipeline() -> StateGraph:
    """Build the LangGraph pipeline with conditional routing by document type.

    Routing:
    - KYC documents:     Classifier → KYC → Fraud → Orchestrator
    - Policy documents:  Classifier → Policy Ingestion → END (no decision needed)
    - Bills/Claims/etc:  Classifier → Claims → Policy → Fraud → Orchestrator
    - Unknown documents: Classifier → Orchestrator

    Returns:
        Compiled StateGraph
    """
    graph = StateGraph(PipelineState)

    # Add nodes
    graph.add_node("classifier", classifier_node)
    graph.add_node("kyc", kyc_node)
    graph.add_node("extraction", extraction_node)
    graph.add_node("policy_ingestion", policy_ingestion_node)
    graph.add_node("fraud", fraud_node)
    graph.add_node("orchestrator", orchestrator_node)

    # Set entry point
    graph.set_entry_point("classifier")

    # Conditional routing after classification
    graph.add_conditional_edges(
        "classifier",
        route_by_doc_type,
        {
            "kyc": "kyc",
            "extraction": "extraction",
            "policy_ingestion": "policy_ingestion",
            "orchestrator": "orchestrator",
        },
    )

    # KYC path: KYC -> Fraud -> Orchestrator
    graph.add_edge("kyc", "fraud")

    # Extraction path: Claims+Policy -> Fraud -> Orchestrator
    graph.add_edge("extraction", "fraud")

    # Policy Ingestion path: directly to END (no decision needed for policy uploads)
    graph.add_edge("policy_ingestion", END)

    # Fraud -> Orchestrator
    graph.add_edge("fraud", "orchestrator")

    # Orchestrator -> END
    graph.add_edge("orchestrator", END)

    return graph.compile()


# Create singleton pipeline instance
pipeline = build_pipeline()


def process_document(
    image_bytes: bytes | None = None,
    image_path: str | None = None,
    case_id: str | None = None,
) -> PipelineState:
    """Process a document through the pipeline.

    Args:
        image_bytes: Raw image bytes
        image_path: Path to image file
        case_id: Optional case identifier

    Returns:
        Final pipeline state with all agent outputs and decision
    """
    if not image_bytes and not image_path:
        raise ValueError("Either image_bytes or image_path must be provided")

    initial_state: PipelineState = {
        "case_id": case_id or "",
        "image_bytes": image_bytes,
        "image_path": image_path or "",
        "current_step": "received",
    }

    result = pipeline.invoke(initial_state)
    return result
