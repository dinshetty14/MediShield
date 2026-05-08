"""Tests for the LangGraph pipeline."""

import pytest

from app.pipeline.state import PipelineState
from app.pipeline.graph import build_pipeline, route_by_doc_type
from app.models.document import DocType
from app.models.agent_outputs import ClassifierOutput


class TestRouting:
    def test_route_kyc_document(self):
        """KYC documents should route to KYC agent."""
        state: PipelineState = {"doc_type": DocType.KYC_DOCUMENT}
        assert route_by_doc_type(state) == "kyc"

    def test_route_claim_form(self):
        """Claim forms should route to claims agent."""
        state: PipelineState = {"doc_type": DocType.CLAIM_FORM}
        assert route_by_doc_type(state) == "claims"

    def test_route_patient_bill(self):
        """Patient bills should route to claims agent."""
        state: PipelineState = {"doc_type": DocType.PATIENT_BILL}
        assert route_by_doc_type(state) == "claims"

    def test_route_medical_report(self):
        """Medical reports should route to claims agent."""
        state: PipelineState = {"doc_type": DocType.MEDICAL_REPORT}
        assert route_by_doc_type(state) == "claims"

    def test_route_prescription(self):
        """Prescriptions should route to claims agent."""
        state: PipelineState = {"doc_type": DocType.PRESCRIPTION}
        assert route_by_doc_type(state) == "claims"

    def test_route_unknown(self):
        """Unknown documents should go directly to orchestrator."""
        state: PipelineState = {"doc_type": DocType.UNKNOWN}
        assert route_by_doc_type(state) == "orchestrator"

    def test_route_none(self):
        """None doc_type should go to claims (default path)."""
        state: PipelineState = {"doc_type": None}
        assert route_by_doc_type(state) == "claims"


class TestPipelineBuild:
    def test_pipeline_builds(self):
        """Pipeline should build successfully."""
        pipeline = build_pipeline()
        assert pipeline is not None

    def test_pipeline_has_all_nodes(self):
        """Pipeline should have all expected nodes."""
        pipeline = build_pipeline()
        graph = pipeline.get_graph()
        node_names = set(graph.nodes.keys())

        expected_nodes = {
            "__start__",
            "classifier",
            "kyc",
            "claims",
            "policy",
            "fraud",
            "orchestrator",
            "__end__",
        }

        assert expected_nodes.issubset(node_names)


class TestPipelineState:
    def test_state_fields(self):
        """PipelineState should accept all expected fields."""
        state: PipelineState = {
            "case_id": "test-123",
            "image_bytes": b"fake image",
            "image_path": "/path/to/image.png",
            "doc_type": DocType.CLAIM_FORM,
            "classifier_output": None,
            "kyc_output": None,
            "claims_output": None,
            "policy_output": None,
            "fraud_output": None,
            "final_decision": None,
            "error": None,
            "current_step": "received",
        }

        assert state["case_id"] == "test-123"
        assert state["doc_type"] == DocType.CLAIM_FORM
