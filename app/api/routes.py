"""API routes for case management."""

import os
import time
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.cases import CaseRepository
from app.db.database import get_db
from app.models.document import CaseStatus, DocType
from app.pipeline.graph import process_document

from .schemas import (
    CaseDetailResponse,
    CaseListResponse,
    CaseResponse,
    HealthResponse,
    OverrideRequest,
    StatsResponse,
)

router = APIRouter()
settings = get_settings()

# Storage directory for uploaded files
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        database="connected",
    )


@router.post("/cases", response_model=CaseResponse)
async def create_case(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a document and create a new case.

    The document will be processed through the pipeline:
    1. Classification
    2. Data extraction (KYC/Claims)
    3. Policy coverage check
    4. Fraud detection
    5. Final decision
    """
    # Validate file type
    allowed_types = {
        "image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif",
        "application/pdf",  # Native Gemini PDF support
        "image/tiff", "image/tif",  # TIFF (converted to PNG)
    }
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type {file.content_type} not allowed. Allowed types: {allowed_types}",
        )

    # Read file content
    content = await file.read()
    file_size = len(content)

    # Save file to storage
    file_ext = Path(file.filename).suffix if file.filename else ".png"
    storage_filename = f"{uuid4()}{file_ext}"
    storage_path = UPLOAD_DIR / storage_filename
    storage_path.write_bytes(content)

    # Create case record
    repo = CaseRepository(db)
    case = repo.create(
        filename=file.filename or "unknown",
        content_type=file.content_type or "image/png",
        size_bytes=file_size,
        storage_path=str(storage_path),
    )

    # Update status to processing
    repo.update_status(case.id, CaseStatus.PROCESSING)

    # Process through pipeline
    start_time = time.perf_counter()
    try:
        # Save original filename for pattern matching, then process
        # Use a temp path with original filename for classifier pattern matching
        original_filename = file.filename or "unknown"
        temp_path = UPLOAD_DIR / original_filename
        temp_path.write_bytes(content)

        result = process_document(
            image_path=str(temp_path),
            case_id=case.id,
        )

        # Clean up temp file if different from storage path
        if str(temp_path) != str(storage_path) and temp_path.exists():
            temp_path.unlink()
        processing_time = time.perf_counter() - start_time

        # Update case with results
        case = repo.update_from_pipeline(case.id, result, processing_time)

    except Exception as e:
        processing_time = time.perf_counter() - start_time
        # Log error and mark case for manual review
        case.status = CaseStatus.ESCALATED.value
        case.decision_justification = f"Processing error: {str(e)}"
        case.processing_time_seconds = processing_time
        db.commit()
        db.refresh(case)

    return CaseResponse.model_validate(case)


@router.get("/cases", response_model=CaseListResponse)
async def list_cases(
    status: str | None = Query(None, description="Filter by status"),
    doc_type: str | None = Query(None, description="Filter by document type"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List all cases with optional filters."""
    repo = CaseRepository(db)

    # Parse filters
    status_filter = None
    if status:
        try:
            status_filter = CaseStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    doc_type_filter = None
    if doc_type:
        doc_type_filter = DocType.from_string(doc_type)

    cases = repo.list(
        status=status_filter,
        doc_type=doc_type_filter,
        limit=limit,
        offset=offset,
    )

    return CaseListResponse(
        cases=[CaseResponse.model_validate(c) for c in cases],
        total=len(cases),
        limit=limit,
        offset=offset,
    )


@router.get("/cases/escalated", response_model=list[CaseResponse])
async def get_escalated_cases(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Get cases that need human review."""
    repo = CaseRepository(db)
    cases = repo.get_escalated(limit=limit)
    return [CaseResponse.model_validate(c) for c in cases]


@router.get("/cases/stats", response_model=StatsResponse)
async def get_stats(db: Session = Depends(get_db)):
    """Get case statistics."""
    repo = CaseRepository(db)
    return repo.get_stats()


@router.get("/cases/{case_id}", response_model=CaseDetailResponse)
async def get_case(case_id: str, db: Session = Depends(get_db)):
    """Get detailed case information including all agent outputs."""
    repo = CaseRepository(db)
    case = repo.get(case_id)

    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    return CaseDetailResponse.model_validate(case)


@router.patch("/cases/{case_id}/override", response_model=CaseResponse)
async def override_decision(
    case_id: str,
    override: OverrideRequest,
    db: Session = Depends(get_db),
):
    """Override a case decision (for human review).

    Only escalated cases can be overridden.
    """
    repo = CaseRepository(db)
    case = repo.get(case_id)

    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if case.status != CaseStatus.ESCALATED.value:
        raise HTTPException(
            status_code=400,
            detail="Only escalated cases can be overridden",
        )

    case = repo.override_decision(
        case_id=case_id,
        new_decision=override.decision,
        override_by=override.override_by,
        reason=override.reason,
    )

    return CaseResponse.model_validate(case)


@router.get("/cases/{case_id}/image")
async def get_case_image(case_id: str, db: Session = Depends(get_db)):
    """Get the document image for a case."""
    from fastapi.responses import FileResponse

    repo = CaseRepository(db)
    case = repo.get(case_id)

    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if not case.storage_path or not Path(case.storage_path).exists():
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(
        case.storage_path,
        media_type=case.content_type,
        filename=case.filename,
    )


@router.get("/analytics/calibration")
async def get_calibration_data(db: Session = Depends(get_db)):
    """Get calibration data for confidence analysis.

    Returns data for plotting calibration curves:
    - Bin-wise accuracy vs confidence
    - ECE (Expected Calibration Error)
    - Overall statistics
    """
    import json
    from collections import defaultdict

    repo = CaseRepository(db)

    # Get all completed cases (approved, rejected, escalated) with decisions
    cases = []
    for status in [CaseStatus.APPROVED, CaseStatus.REJECTED, CaseStatus.ESCALATED]:
        cases.extend(repo.list(status=status, limit=200))

    if not cases:
        return {
            "predictions": [],
            "bins": [],
            "ece": None,
            "overall_accuracy": None,
            "mean_confidence": None,
            "total_cases": 0,
        }

    # Collect predictions: we need ground truth to determine correctness
    # For now, use classifier confidence and assume "processed" status means correct classification
    # For real calibration, we'd need ground truth labels
    predictions = []
    for case in cases:
        if case.decision_confidence is not None:
            # Load classifier output to get classification confidence
            classifier_output = case.classifier_output
            if classifier_output:
                if isinstance(classifier_output, str):
                    classifier_output = json.loads(classifier_output)
                conf = classifier_output.get("confidence", case.decision_confidence)
            else:
                conf = case.decision_confidence

            # For calibration, we approximate "correct" as:
            # - Decision was made (not escalated for low confidence)
            # - High confidence cases that completed processing
            correct = case.decision in ["approve", "reject"] and case.decision_confidence >= 0.5

            predictions.append({
                "case_id": case.id,
                "confidence": conf,
                "correct": correct,
                "decision": case.decision,
            })

    if not predictions:
        return {
            "predictions": predictions,
            "bins": [],
            "ece": None,
            "overall_accuracy": None,
            "mean_confidence": None,
            "total_cases": 0,
        }

    # Calculate bins
    n_bins = 10
    bin_data = defaultdict(lambda: {"correct": 0, "total": 0, "sum_conf": 0})

    for pred in predictions:
        bin_idx = min(int(pred["confidence"] * n_bins), n_bins - 1)
        bin_data[bin_idx]["total"] += 1
        bin_data[bin_idx]["sum_conf"] += pred["confidence"]
        if pred["correct"]:
            bin_data[bin_idx]["correct"] += 1

    bins = []
    ece_sum = 0
    total_samples = len(predictions)

    for i in range(n_bins):
        bin_info = bin_data[i]
        if bin_info["total"] > 0:
            accuracy = bin_info["correct"] / bin_info["total"]
            mean_conf = bin_info["sum_conf"] / bin_info["total"]
            ece_sum += abs(accuracy - mean_conf) * bin_info["total"]
        else:
            accuracy = None
            mean_conf = (i + 0.5) / n_bins

        bins.append({
            "bin_start": i / n_bins,
            "bin_end": (i + 1) / n_bins,
            "count": bin_info["total"],
            "accuracy": accuracy,
            "mean_confidence": mean_conf,
        })

    ece = ece_sum / total_samples if total_samples > 0 else None
    overall_accuracy = sum(1 for p in predictions if p["correct"]) / len(predictions)
    mean_confidence = sum(p["confidence"] for p in predictions) / len(predictions)

    return {
        "predictions": predictions,
        "bins": bins,
        "ece": ece,
        "overall_accuracy": overall_accuracy,
        "mean_confidence": mean_confidence,
        "total_cases": len(predictions),
    }


@router.post("/policies/index")
async def index_policies():
    """Index all policy PDFs for RAG retrieval."""
    from app.agents.policy import PolicyAgent

    policy_agent = PolicyAgent()
    count = policy_agent.index_policies()

    return {"message": f"Indexed {count} policy chunks", "count": count}


@router.get("/cases/{case_id}/report")
async def download_case_report(case_id: str, db: Session = Depends(get_db)):
    """Download a PDF audit report for a case.

    Generates a comprehensive PDF containing:
    - Case summary and status
    - Final decision with justification
    - All agent outputs (Classification, KYC, Claims, Policy, Fraud)
    - Override information (if applicable)
    """
    from fastapi.responses import Response

    from .pdf_export import generate_case_report

    repo = CaseRepository(db)
    case = repo.get(case_id)

    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Generate PDF
    pdf_bytes = generate_case_report(case)

    # Return as downloadable file
    filename = f"medishield_case_{case_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        },
    )
