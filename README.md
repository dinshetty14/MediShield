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
# Evaluate pipeline on test dataset
uv run python scripts/evaluate.py --limit 5
```

### 3. Start Backend

```bash
uv run uvicorn app.main:app --reload
```

API available at http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- Health check: http://localhost:8000/api/health

### 4. Start Frontend

```bash
cd frontend
npm install
npm run dev
```

UI available at http://localhost:3000
- **Dashboard** - Upload documents, view cases, download PDF reports
- **Review Queue** - Handle escalated cases with override capability
- **Analytics** - Confidence calibration curves and ECE metrics

## Architecture

```
RECEIVED → CLASSIFIED → [Route by Doc Type] → ...
  - KYC Documents:    KYC → FRAUD → ORCHESTRATOR → DECIDED
  - Policy Documents: POLICY_INGESTION → END (stored in ChromaDB)
  - Bills/Claims/etc: CLAIMS → POLICY → FRAUD → ORCHESTRATOR → DECIDED
  - Unknown:          ORCHESTRATOR → DECIDED
```

**Agents:**
| Agent | Strategy |
|-------|----------|
| Classifier | Filename regex → OCR keywords → LLM fallback |
| KYC | Vision LLM |
| Claims | OCR + regex extraction → LLM fallback |
| Policy | RAG over policy PDFs (checks coverage) |
| Policy Ingestion | Docling PDF parsing → ChromaDB storage |
| Fraud | Rule-based detection (duplicates, frequency, amount anomalies) |
| Orchestrator | Aggregates decisions |

## Optimizations

The pipeline uses a smart fallback strategy to minimize LLM calls:

1. **Filename Pattern Matching** - Instant classification for files like `bill_*.png`
2. **EasyOCR Extraction** - Extract amounts, dates without LLM
3. **Rule-based Fraud Detection** - Check duplicates, frequency anomalies without LLM
4. **Cached OCR Reader** - Initialize once, reuse for all documents
5. **LLM Fallback** - Only called when regex/OCR cannot classify or extract

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/cases` | Upload document |
| GET | `/api/cases` | List cases |
| GET | `/api/cases/{id}` | Get case detail |
| GET | `/api/cases/{id}/report` | Download PDF audit report |
| PATCH | `/api/cases/{id}/override` | Override decision |
| GET | `/api/cases/escalated` | Get review queue |
| GET | `/api/cases/stats` | Get case statistics |
| GET | `/api/analytics/calibration` | Get confidence calibration data |
| POST | `/api/policies/index` | Index policy PDFs |

## Project Structure

```
MediShield/
├── app/
│   ├── agents/
│   │   ├── base.py           # Base agent with LLM integration
│   │   ├── classifier.py     # Regex → OCR → LLM classifier
│   │   ├── claims.py         # OCR → LLM claims extraction
│   │   ├── fraud.py          # Rule-based fraud detection
│   │   ├── kyc.py            # KYC validation
│   │   ├── policy.py         # Policy RAG agent
│   │   └── orchestrator.py   # Final decision maker
│   ├── pipeline/
│   │   ├── graph.py          # LangGraph pipeline
│   │   └── state.py          # Pipeline state definition
│   ├── api/                  # FastAPI routes
│   ├── db/                   # SQLAlchemy models
│   ├── models/               # Pydantic schemas
│   ├── rag/                  # Policy document retrieval
│   └── main.py               # FastAPI app
├── frontend/                 # Next.js UI
├── dataset/                  # Test images
├── policies/                 # Policy PDFs for RAG
├── tests/                    # Pytest tests
└── scripts/
    ├── evaluate.py           # Pipeline evaluation
    └── calibration_plot.py   # Confidence calibration curves
```

## Testing

```bash
# Run unit tests
uv run python -m pytest tests/ -v

# Evaluate on test dataset
uv run python scripts/evaluate.py --limit 5

# Test policy flow
uv run python scripts/test_policy_flow.py
```

## Decision Logic

- **APPROVE**: KYC passed + claim valid + covered + fraud score < 0.3
- **REJECT**: KYC failed OR not covered OR invalid schema
- **ESCALATE**: fraud score >= 0.3 OR any confidence < 0.6 OR duplicate detected

## Fraud Detection

The fraud agent detects:
- **Duplicate claims** - Same amount submitted within 24 hours
- **Frequency anomaly** - More than 5 claims in 30 days
- **Amount anomaly** - Claim > 2x historical average

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google Gemini API key (required) |
| `DATABASE_URL` | SQLite/PostgreSQL URL (default: sqlite:///./medishield.db) |
| `CHROMA_PERSIST_DIR` | Vector store path (default: ./chroma_db) |
| `LANGCHAIN_TRACING_V2` | Enable LangSmith tracing (true/false) |
| `LANGCHAIN_API_KEY` | LangSmith API key (optional) |
| `LANGCHAIN_PROJECT` | LangSmith project name (default: medishield) |

## Supported File Formats

| Format | Support |
|--------|---------|
| PNG | Full support |
| JPEG/JPG | Full support |
| PDF | Native Gemini support |
| TIFF | Converted to PNG |
| WebP | Full support |
| GIF | Full support |

## Document Categories

- Patient Bills
- Claim Forms
- KYC Documents
- Medical Reports
- Prescriptions
- Policy Documents (ingested to ChromaDB for RAG)
- Unknown

## Policy RAG Setup

```bash
# Create sample policy PDF
uv run python scripts/create_sample_policy.py

# Index policies via API
curl -X POST http://localhost:8000/api/policies/index

# Or via Python
uv run python -c "from app.agents.policy import PolicyAgent; print(PolicyAgent().index_policies())"
```

## Bonus Features

### Multi-language OCR
OCR supports English, Hindi, and Spanish documents out of the box.

### LangSmith Tracing
Enable observability by setting environment variables:
```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_xxx...
LANGCHAIN_PROJECT=medishield
```
View traces at [smith.langchain.com](https://smith.langchain.com)

### Confidence Calibration
Generate calibration plots to analyze model confidence:
```bash
# Via CLI script (uses ground truth labels)
uv run python scripts/calibration_plot.py --limit 20
# Output: calibration_curve.png
```

Or view in the UI: Navigate to **Analytics** tab to see:
- Calibration curve (confidence vs accuracy)
- Confidence score distribution histogram
- ECE (Expected Calibration Error) metric
- Model interpretation (overconfident/underconfident)

### PDF Audit Export
Download case reports as PDF:
```bash
# Via API
curl http://localhost:8000/api/cases/{case_id}/report --output report.pdf
```

Or click the **PDF** link in the Report column on the Dashboard.

## Reset Database

```bash
# Stop server, then delete data
rm medishield.db
rm -rf chroma_db

# Restart server
uv run uvicorn app.main:app

# Re-index policies
curl -X POST http://localhost:8000/api/policies/index
```
