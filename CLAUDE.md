# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**MediShield AI-Powered Document Intake System** — A multi-agent pipeline for automating health insurance claim document processing. The system classifies, validates, extracts data, and makes Approve/Reject/Escalate decisions on incoming insurance documents using vision LLMs and specialized agents.

**Assignment Context:** Assignment 02 (Multimodal AI) from AI Codebasics course. Full requirements in `assignment_02_multimodal_ai.md`.

## Architecture

Multi-agent pipeline orchestrated via **LangGraph**:

```
RECEIVED → CLASSIFIED → [PARALLEL: KYC + CLAIMS + POLICY] → FRAUD_CHECK → AGGREGATED → DECIDED
```

**Agents:**
- **Classifier** — vision LLM identifies document type
- **KYC** — validates identity documents, checks expiry, detects tampering
- **Claims** — extracts ICD-10/CPT codes, amounts, provider details
- **Policy** — RAG over policy PDFs (Docling + ChromaDB/Qdrant)
- **Fraud Detection** — analyzes patient history, scores fraud risk
- **Orchestrator** — aggregates outputs, makes final decision with confidence

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

# Reference classifier (Gemini only)
uv run python reference_only/main.py --limit 5
```

**Environment Setup:**
```bash
cp .env.example .env
# Add GEMINI_API_KEY (required for reference implementation)
# Add ANTHROPIC_API_KEY (for Claude vision models in full implementation)
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
- Unknown

**Routing:**
| Category | Queue |
|----------|-------|
| Patient Bills | `billing_queue` |
| Claim Forms | `claims_queue` |
| KYC Documents | `verification_queue` |
| Medical Reports | `medical_review_queue` |
| Prescriptions | `medical_review_queue` |
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
