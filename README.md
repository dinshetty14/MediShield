# MediShield AI-Powered Document Intake System

A multi-agent pipeline for automating health insurance claim document processing using vision LLMs, OCR, and LangGraph.

## Quick Start

### 1. Setup Environment

```bash
# Navigate to project
cd MediShield

# Copy environment file and add API key
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# Install dependencies
uv sync --native-tls
```

### 2. Run Evaluation

```bash
# Standard pipeline (uses LLM for all agents)
uv run python scripts/evaluate.py --limit 5

# Fast pipeline (OCR-first, minimal LLM calls)
uv run python scripts/evaluate_fast.py --limit 5
```

### 3. Start Backend (Optional)

```bash
uv run uvicorn app.main:app --reload
```

API available at http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- Health check: http://localhost:8000/api/health

### 4. Start Frontend (Optional)

```bash
cd frontend
npm install
npm run dev
```

UI available at http://localhost:3000

## Architecture

```
RECEIVED → CLASSIFIED → [KYC|CLAIMS] → POLICY → FRAUD → ORCHESTRATOR → DECIDED
```

**Agents:**
| Agent | Standard Pipeline | Fast Pipeline |
|-------|-------------------|---------------|
| Classifier | Vision LLM | Filename regex + OCR + LLM fallback |
| KYC | Vision LLM | Vision LLM |
| Claims | Vision LLM | EasyOCR + regex extraction |
| Policy | RAG over policy PDFs | RAG (skips if no policies) |
| Fraud | LLM analysis | Rule-based detection |
| Orchestrator | Aggregates decisions | Aggregates decisions |

## Performance Comparison

| Metric | Standard Pipeline | Fast Pipeline |
|--------|-------------------|---------------|
| LLM calls per doc | 3-4 | 0-1 (for filename-matched docs) |
| Time per doc | ~20s | ~6-7s |
| Classification accuracy | 100% | 100% |
| Decision accuracy | 100% | 100% |

## Optimizations (Fast Pipeline)

1. **Filename Pattern Matching** - Instant classification for files like `bill_*.png`
2. **EasyOCR Extraction** - Extract amounts, dates without LLM
3. **Rule-based Fraud Detection** - Check duplicates, frequency anomalies without LLM
4. **Cached OCR Reader** - Initialize once, reuse for all documents

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/cases` | Upload document |
| GET | `/api/cases` | List cases |
| GET | `/api/cases/{id}` | Get case detail |
| PATCH | `/api/cases/{id}/override` | Override decision |
| GET | `/api/cases/escalated` | Get review queue |
| POST | `/api/policies/index` | Index policy PDFs |

## Project Structure

```
MediShield/
├── app/
│   ├── agents/
│   │   ├── classifier.py      # LLM-based classifier
│   │   ├── fast_classifier.py # Filename + OCR classifier
│   │   ├── claims.py          # LLM-based extraction
│   │   ├── fast_claims.py     # OCR-based extraction
│   │   ├── fraud.py           # LLM-based fraud detection
│   │   ├── rule_fraud.py      # Rule-based fraud detection
│   │   ├── kyc.py             # KYC validation
│   │   ├── policy.py          # Policy RAG agent
│   │   └── orchestrator.py    # Final decision maker
│   ├── pipeline/
│   │   ├── graph.py           # Standard LangGraph pipeline
│   │   └── fast_graph.py      # Optimized pipeline
│   ├── api/                   # FastAPI routes
│   ├── db/                    # SQLAlchemy models
│   ├── models/                # Pydantic schemas
│   ├── rag/                   # Policy document retrieval
│   └── main.py                # FastAPI app
├── frontend/                  # Next.js UI
├── dataset/                   # Test images
├── policies/                  # Policy PDFs for RAG
├── tests/                     # Pytest tests
└── scripts/
    ├── evaluate.py            # Standard evaluation
    └── evaluate_fast.py       # Fast evaluation
```

## Testing

```bash
# Run unit tests
uv run python -m pytest tests/ -v

# Standard evaluation
uv run python scripts/evaluate.py --limit 5

# Fast evaluation (recommended)
uv run python scripts/evaluate_fast.py --limit 5
```

## Decision Logic

- **APPROVE**: KYC passed + claim valid + covered + fraud score < 0.3
- **REJECT**: KYC failed OR not covered OR invalid schema
- **ESCALATE**: fraud score ≥ 0.3 OR any confidence < 0.6

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google Gemini API key (required) |
| `DATABASE_URL` | SQLite/PostgreSQL URL (default: sqlite:///./medishield.db) |
| `CHROMA_PERSIST_DIR` | Vector store path (default: ./chroma_db) |

## Document Categories

- Patient Bills
- Claim Forms
- KYC Documents
- Medical Reports
- Prescriptions
- Unknown
