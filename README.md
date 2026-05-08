# MediShield AI-Powered Document Intake System

A multi-agent pipeline for automating health insurance claim document processing using vision LLMs and LangGraph.

## Quick Start

### 1. Setup Environment

```bash
# Clone and navigate to project
cd MediShield

# Copy environment file and add API keys
cp .env.example .env
# Edit .env and add:
# - ANTHROPIC_API_KEY (required)
# - GEMINI_API_KEY (optional, for reference implementation)

# Install dependencies
uv sync --native-tls
```

### 2. Start Backend

```bash
uv run uvicorn app.main:app --reload
```

API available at http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- Health check: http://localhost:8000/api/health

### 3. Start Frontend

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
| Agent | Function |
|-------|----------|
| Classifier | Vision LLM identifies document type |
| KYC | Validates identity documents |
| Claims | Extracts ICD-10/CPT codes, amounts |
| Policy | RAG over policy PDFs for coverage |
| Fraud | Detects anomalies, scores risk |
| Orchestrator | Makes final Approve/Reject/Escalate decision |

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
│   ├── agents/          # 6 specialized agents
│   ├── api/             # FastAPI routes
│   ├── db/              # SQLAlchemy models
│   ├── models/          # Pydantic schemas
│   ├── pipeline/        # LangGraph workflow
│   ├── rag/             # Policy document retrieval
│   └── main.py          # FastAPI app
├── frontend/            # Next.js UI
├── dataset/             # Test images
├── policies/            # Policy PDFs for RAG
├── tests/               # Pytest tests
└── scripts/
    └── evaluate.py      # Evaluation script
```

## Testing

```bash
# Run unit tests
uv run python -m pytest tests/ -v

# Run evaluation on dataset
uv run python scripts/evaluate.py --limit 5
```

## Decision Logic

- **APPROVE**: KYC passed + claim valid + covered + fraud score < 0.3
- **REJECT**: KYC failed OR not covered OR invalid schema
- **ESCALATE**: fraud score ≥ 0.3 OR any confidence < 0.6

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Claude API key (required) |
| `GEMINI_API_KEY` | Gemini API key (optional) |
| `DATABASE_URL` | SQLite/PostgreSQL URL |
| `CHROMA_PERSIST_DIR` | Vector store path |
