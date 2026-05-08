"""Case repository for database operations."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.decisions import FinalDecision
from app.models.document import CaseStatus, DocType
from app.pipeline.state import PipelineState

from .models import CaseModel


class CaseRepository:
    """Repository for case CRUD operations."""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        filename: str,
        content_type: str,
        size_bytes: int,
        storage_path: str | None = None,
    ) -> CaseModel:
        """Create a new case."""
        case = CaseModel(
            id=str(uuid4()),
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            storage_path=storage_path,
            status=CaseStatus.RECEIVED.value,
        )
        self.db.add(case)
        self.db.commit()
        self.db.refresh(case)
        return case

    def get(self, case_id: str) -> CaseModel | None:
        """Get a case by ID."""
        return self.db.query(CaseModel).filter(CaseModel.id == case_id).first()

    def list(
        self,
        status: CaseStatus | None = None,
        doc_type: DocType | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CaseModel]:
        """List cases with optional filters."""
        query = self.db.query(CaseModel)

        if status:
            query = query.filter(CaseModel.status == status.value)
        if doc_type:
            query = query.filter(CaseModel.doc_type == doc_type.value)

        return query.order_by(desc(CaseModel.created_at)).offset(offset).limit(limit).all()

    def update_status(self, case_id: str, status: CaseStatus) -> CaseModel | None:
        """Update case status."""
        case = self.get(case_id)
        if case:
            case.status = status.value
            case.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(case)
        return case

    def update_from_pipeline(
        self,
        case_id: str,
        pipeline_state: PipelineState,
        processing_time: float,
    ) -> CaseModel | None:
        """Update case with pipeline results."""
        case = self.get(case_id)
        if not case:
            return None

        # Update classification
        if pipeline_state.get("doc_type"):
            case.doc_type = pipeline_state["doc_type"].value

        # Update agent outputs
        classifier_out = pipeline_state.get("classifier_output")
        if classifier_out:
            case.classifier_output = classifier_out.model_dump(mode="json")
            case.queue = classifier_out.routing_tags[-1].replace("queue:", "") if classifier_out.routing_tags else None

        kyc_out = pipeline_state.get("kyc_output")
        if kyc_out:
            case.kyc_output = kyc_out.model_dump(mode="json")

        claims_out = pipeline_state.get("claims_output")
        if claims_out:
            case.claims_output = claims_out.model_dump(mode="json")

        policy_out = pipeline_state.get("policy_output")
        if policy_out:
            case.policy_output = policy_out.model_dump(mode="json")

        fraud_out = pipeline_state.get("fraud_output")
        if fraud_out:
            case.fraud_output = fraud_out.model_dump(mode="json")

        # Update decision
        final_decision: FinalDecision | None = pipeline_state.get("final_decision")
        if final_decision:
            case.decision = final_decision.decision.value
            case.decision_confidence = final_decision.confidence
            case.decision_justification = final_decision.justification

            # Map decision to status
            status_map = {
                "approve": CaseStatus.APPROVED,
                "reject": CaseStatus.REJECTED,
                "escalate": CaseStatus.ESCALATED,
            }
            case.status = status_map.get(final_decision.decision.value, CaseStatus.PROCESSING).value

        case.processing_time_seconds = processing_time
        case.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(case)
        return case

    def override_decision(
        self,
        case_id: str,
        new_decision: str,
        override_by: str,
        reason: str,
    ) -> CaseModel | None:
        """Override a case decision (for human review)."""
        case = self.get(case_id)
        if not case:
            return None

        case.overridden = True
        case.override_by = override_by
        case.override_reason = reason
        case.override_decision = new_decision
        case.override_timestamp = datetime.utcnow()

        # Update status based on override
        status_map = {
            "approve": CaseStatus.APPROVED,
            "reject": CaseStatus.REJECTED,
        }
        if new_decision in status_map:
            case.status = status_map[new_decision].value

        case.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(case)
        return case

    def get_escalated(self, limit: int = 100) -> list[CaseModel]:
        """Get escalated cases for human review."""
        return (
            self.db.query(CaseModel)
            .filter(CaseModel.status == CaseStatus.ESCALATED.value)
            .filter(CaseModel.overridden == False)
            .order_by(CaseModel.created_at)
            .limit(limit)
            .all()
        )

    def get_stats(self) -> dict:
        """Get case statistics."""
        total = self.db.query(CaseModel).count()

        status_counts = {}
        for status in CaseStatus:
            count = self.db.query(CaseModel).filter(CaseModel.status == status.value).count()
            status_counts[status.value] = count

        return {
            "total": total,
            "by_status": status_counts,
        }
