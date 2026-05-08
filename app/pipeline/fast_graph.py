"""Optimized LangGraph pipeline using fast agents (OCR-first, LLM-fallback)."""

from typing import Literal

from langgraph.graph import END, StateGraph

from app.agents.fast_classifier import FastClassifierAgent
from app.agents.fast_claims import FastClaimsAgent
from app.agents.rule_fraud import RuleFraudAgent
from app.agents.kyc import KYCAgent
from app.agents.orchestrator import OrchestratorAgent
from app.agents.policy import PolicyAgent
from app.models.document import DocType

from .state import PipelineState


# Initialize fast agents
_classifier = FastClassifierAgent()
_kyc = KYCAgent()
_claims = FastClaimsAgent()
_policy = PolicyAgent()
_fraud = RuleFraudAgent()  # Rule-based, no LLM
_orchestrator = OrchestratorAgent()


def classifier_node(state: PipelineState) -> PipelineState:
    """Classify using filename/OCR first, LLM fallback."""
    image_source = state.get("image_bytes") or state.get("image_path")
    if not image_source:
        return {"error": "No image provided", "current_step": "classifier"}

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
    return {"kyc_output": output, "current_step": "kyc_complete"}


def claims_node(state: PipelineState) -> PipelineState:
    """Extract claims using OCR first, LLM fallback."""
    image_source = state.get("image_bytes") or state.get("image_path")
    output = _claims.process(image_source)
    return {"claims_output": output, "current_step": "claims_complete"}


def policy_node(state: PipelineState) -> PipelineState:
    """Check policy coverage."""
    claims_output = state.get("claims_output")
    output = _policy.process(claims_output=claims_output)
    return {"policy_output": output, "current_step": "policy_complete"}


def fraud_node(state: PipelineState) -> PipelineState:
    """Check for fraud indicators."""
    claims_output = state.get("claims_output")
    output = _fraud.process(claims_output=claims_output)
    return {"fraud_output": output, "current_step": "fraud_complete"}


def orchestrator_node(state: PipelineState) -> PipelineState:
    """Make final decision."""
    output = _orchestrator.process(
        classifier_output=state.get("classifier_output"),
        kyc_output=state.get("kyc_output"),
        claims_output=state.get("claims_output"),
        policy_output=state.get("policy_output"),
        fraud_output=state.get("fraud_output"),
    )
    return {"final_decision": output, "current_step": "decided"}


def route_by_doc_type(state: PipelineState) -> Literal["kyc", "claims", "orchestrator"]:
    """Route based on document type."""
    doc_type = state.get("doc_type")
    if doc_type == DocType.KYC_DOCUMENT:
        return "kyc"
    elif doc_type == DocType.UNKNOWN:
        return "orchestrator"
    else:
        return "claims"


def build_fast_pipeline() -> StateGraph:
    """Build optimized pipeline with fast agents."""
    graph = StateGraph(PipelineState)

    graph.add_node("classifier", classifier_node)
    graph.add_node("kyc", kyc_node)
    graph.add_node("claims", claims_node)
    graph.add_node("policy", policy_node)
    graph.add_node("fraud", fraud_node)
    graph.add_node("orchestrator", orchestrator_node)

    graph.set_entry_point("classifier")

    graph.add_conditional_edges(
        "classifier",
        route_by_doc_type,
        {"kyc": "kyc", "claims": "claims", "orchestrator": "orchestrator"},
    )

    graph.add_edge("kyc", "fraud")
    graph.add_edge("claims", "policy")
    graph.add_edge("policy", "fraud")
    graph.add_edge("fraud", "orchestrator")
    graph.add_edge("orchestrator", END)

    return graph.compile()


# Create fast pipeline instance
fast_pipeline = build_fast_pipeline()


def process_document_fast(
    image_bytes: bytes | None = None,
    image_path: str | None = None,
    case_id: str | None = None,
) -> PipelineState:
    """Process document using optimized pipeline."""
    if not image_bytes and not image_path:
        raise ValueError("Either image_bytes or image_path must be provided")

    initial_state: PipelineState = {
        "case_id": case_id or "",
        "image_bytes": image_bytes,
        "image_path": image_path or "",
        "current_step": "received",
    }

    return fast_pipeline.invoke(initial_state)
