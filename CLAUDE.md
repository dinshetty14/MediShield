# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**MediShield AI-Powered Document Intake System** — A multi-agent pipeline for automating health insurance claim document processing. The system classifies, validates, extracts data, and makes Approve/Reject/Escalate decisions on incoming insurance documents using vision LLMs and specialized agents.

**Assignment Context:** Assignment 02 (Multimodal AI) from AI Codebasics course. Full requirements in `assignment_02_multimodal_ai.md`.

## Architecture

Multi-agent pipeline orchestrated via **LangGraph** with conditional routing:

```
RECEIVED → CLASSIFIED → [Route by Doc Type]
  - KYC Documents:    KYC → FRAUD → ORCHESTRATOR → DECIDED
  - Policy Documents: POLICY_INGESTION → END (Docling + ChromaDB)
  - Bills/Claims/etc: CLAIMS → POLICY → FRAUD → ORCHESTRATOR → DECIDED
  - Unknown:          ORCHESTRATOR → DECIDED
```

**Agents:**
- **Classifier** — regex → OCR → vision LLM (fallback strategy)
- **KYC** — validates identity documents, checks expiry, detects tampering
- **Claims** — OCR + regex extraction → vision LLM fallback
- **Policy** — RAG over indexed policy PDFs (ChromaDB)
- **Policy Ingestion** — Docling PDF parsing → ChromaDB storage
- **Fraud Detection** — rule-based (duplicates, frequency, amount anomalies)
- **Orchestrator** — aggregates outputs, makes final decision with confidence

**Bonus Features Implemented:**
- Multi-language OCR (English, Hindi, Spanish)
- LangSmith tracing integration
- Confidence calibration (CLI script + UI Analytics page)
- PDF audit export (UI button + API endpoint)

## Supported File Formats

| Format | Support |
|--------|---------|
| PNG, JPEG | Full support |
| PDF | Native Gemini support |
| TIFF | Converted to PNG |
| WebP, GIF | Full support |

**Decision Logic:**
- `APPROVE`: KYC passed + claim valid + covered + fraud score < 0.3
- `REJECT`: KYC failed OR procedure not covered OR schema invalid
- `ESCALATE`: fraud score ≥ 0.3 OR any agent confidence < 0.6

## Development Commands

```bash
# Start backend API server
uv run uvicorn app.main:app --reload

# Start frontend (in separate terminal)
cd frontend && npm run dev

# Run tests
uv run python -m pytest tests/ -v

# Run evaluation on test dataset
uv run python scripts/evaluate.py --limit 5

# Generate confidence calibration plot
uv run python scripts/calibration_plot.py --limit 20

# Reference classifier (Gemini only)
uv run python reference_only/main.py --limit 5
```

**Environment Setup:**
```bash
cp .env.example .env
# Add GEMINI_API_KEY (required for reference implementation)
# Add ANTHROPIC_API_KEY (for Claude vision models in full implementation)

# Optional: Enable LangSmith tracing
# LANGCHAIN_TRACING_V2=true
# LANGCHAIN_API_KEY=lsv2_pt_xxx...
# LANGCHAIN_PROJECT=medishield
```

**Dependencies:**
```bash
uv sync --native-tls  # Install all dependencies
```

## Key Directories

- `dataset/` — 50 synthetic document images (bills, claims, IDs, prescriptions)
- `reference_only/` — baseline single-agent classifier using Gemini 2.0 (read-only reference)
  - `jupyter_files/` — tutorial notebooks on RAG, LangChain, embeddings, routing, guardrails, evals, observability

## Document Categories

Classify into exactly these categories (case-insensitive):
- Patient Bills
- Claim Forms
- KYC Documents
- Medical Reports
- Prescriptions
- Policy Documents (insurance policy PDFs for RAG ingestion)
- Unknown

**Routing:**
| Category | Queue |
|----------|-------|
| Patient Bills | `billing_queue` |
| Claim Forms | `claims_queue` |
| KYC Documents | `verification_queue` |
| Medical Reports | `medical_review_queue` |
| Prescriptions | `medical_review_queue` |
| Policy Documents | `policy_ingestion_queue` |
| Unknown | `manual_review_queue` |

## Rate Limiting

Gemini free tier (15 RPM):
- Default 4s delay between requests
- Automatic retry on 429 with exponential backoff
- Parses API's `retryDelay` hint from error messages
- Stops pipeline on daily quota exhaustion

## Agent Output Contracts

**All agents must return:** structured JSON with `confidence: float` (0-1)

**Claims Agent schema:**
```json
{
  "extracted_fields": {
    "claim_amount": "float",
    "icd_10_codes": ["str"],
    "cpt_codes": ["str"],
    "provider_npi": "str",
    "service_date": "str"
  },
  "schema_valid": "bool",
  "validation_errors": ["str"],
  "confidence": "float"
}
```

## Success Metrics

- Classification accuracy ≥ 95%
- Processing time < 5 seconds per document
- Decision Correctness ≥ 60% (minimum passing)

## Constraints

- All agent communication must use Pydantic models or TypedDicts
- All LLM calls must have retry logic
- Validate LLM outputs against expected schema
- Route OCR failures to manual review
- Load document categories from config (no hardcoding)

## Bonus Features

| Feature | Location | Usage |
|---------|----------|-------|
| Multi-language OCR | `app/agents/classifier.py`, `app/agents/claims.py` | Supports English, Hindi, Spanish |
| LangSmith Tracing | `app/pipeline/graph.py` | Set `LANGCHAIN_TRACING_V2=true` in `.env` |
| Calibration Plot | `scripts/calibration_plot.py` | CLI: `uv run python scripts/calibration_plot.py` |
| Calibration UI | `frontend/src/app/analytics/page.tsx` | Navigate to Analytics tab in UI |
| Calibration API | `app/api/routes.py` | `GET /api/analytics/calibration` |
| PDF Audit Export | `app/api/pdf_export.py` | Click PDF link in Dashboard or `GET /api/cases/{id}/report` |

## Frontend Pages

| Page | Path | Description |
|------|------|-------------|
| Dashboard | `/` | Upload documents, view cases, download PDF reports |
| Case Detail | `/cases/[id]` | Full case info with all agent outputs |
| Review Queue | `/review` | Escalated cases with human override |
| Analytics | `/analytics` | Confidence calibration curves, ECE metrics |
