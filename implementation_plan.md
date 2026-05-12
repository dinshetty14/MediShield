# MediShield Implementation Plan

## Overview

Build a multi-agent document intake system using LangGraph that processes insurance documents through classification, validation, extraction, fraud detection, and final decision-making.

---

## Phase 1: Project Setup & Infrastructure

### 1.1 Project Structure
```
medishield/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app entry
│   ├── config.py               # Settings, env vars
│   ├── models/                 # Pydantic schemas
│   │   ├── __init__.py
│   │   ├── document.py         # Document, Case models
│   │   ├── agent_outputs.py    # Agent response schemas
│   │   └── decisions.py        # Decision enums, final output
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py             # Base agent class
│   │   ├── classifier.py       # Document classifier
│   │   ├── kyc.py              # KYC validation
│   │   ├── claims.py           # Claims extraction
│   │   ├── policy.py           # Policy RAG agent
│   │   ├── fraud.py            # Fraud detection
│   │   └── orchestrator.py     # Final decision maker
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── graph.py            # LangGraph state machine
│   │   └── state.py            # Pipeline state definition
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── ingestion.py        # Docling PDF parsing
│   │   └── retriever.py        # ChromaDB retrieval
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py           # API endpoints
│   │   └── deps.py             # Dependencies
│   └── db/
│       ├── __init__.py
│       └── cases.py            # Case storage (SQLite/PostgreSQL)
├── frontend/                   # Next.js app
├── dataset/                    # Test images (existing)
├── policies/                   # Sample policy PDFs
├── tests/
├── pyproject.toml
└── .env
```

### 1.2 Dependencies (pyproject.toml)
```toml
[project]
name = "medishield"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.30.0",
    "python-dotenv>=1.0.0",
    "pydantic>=2.7.0",
    "langgraph>=0.2.0",
    "langchain>=0.2.0",
    "langchain-anthropic>=0.1.0",
    "langchain-google-genai>=1.0.0",
    "chromadb>=0.5.0",
    "docling>=2.0.0",
    "pillow>=10.0.0",
    "httpx>=0.27.0",
]
```

### 1.3 Environment Variables
```
ANTHROPIC_API_KEY=           # Claude vision models
GEMINI_API_KEY=              # Gemini fallback
DATABASE_URL=sqlite:///./medishield.db
CHROMA_PERSIST_DIR=./chroma_db
```

---

## Phase 2: Core Models & State

### 2.1 Pydantic Models

**Document Categories:**
```python
class DocType(str, Enum):
    CLAIM_FORM = "Claim Forms"
    ID_DOCUMENT = "KYC Documents"
    PATIENT_BILL = "Patient Bills"
    MEDICAL_REPORT = "Medical Reports"
    PRESCRIPTION = "Prescriptions"
    UNKNOWN = "Unknown"
```

**Agent Output Base:**
```python
class AgentOutput(BaseModel):
    agent_name: str
    confidence: float  # 0.0 - 1.0
    timestamp: datetime
    errors: list[str] = []
```

**Pipeline State (LangGraph):**
```python
class PipelineState(TypedDict):
    case_id: str
    image_bytes: bytes
    image_path: str
    doc_type: DocType | None
    classifier_output: ClassifierOutput | None
    kyc_output: KYCOutput | None
    claims_output: ClaimsOutput | None
    policy_output: PolicyOutput | None
    fraud_output: FraudOutput | None
    final_decision: Decision | None
    error: str | None
```

---

## Phase 3: Agent Implementation

### 3.1 Classifier Agent
- **Input:** Raw image bytes
- **Model:** Claude claude-sonnet-4-20250514 (vision) or Gemini 2.0 Flash
- **Output:** `{ doc_type, confidence, routing_tags }`
- **Logic:** Adapt prompt from `reference_only/main.py`

### 3.2 KYC Agent
- **Input:** Image (ID document)
- **Output:**
  ```python
  class KYCOutput(AgentOutput):
      kyc_passed: bool
      document_type: str  # Aadhaar, PAN, Passport
      expiry_date: date | None
      is_expired: bool
      tampering_flags: list[str]
  ```
- **Checks:** Expiry validation, visual anomaly detection

### 3.3 Claims Agent
- **Input:** Image (claim form, bill, medical report)
- **Output:**
  ```python
  class ClaimsOutput(AgentOutput):
      claim_amount: float | None
      icd_10_codes: list[str]
      cpt_codes: list[str]
      provider_npi: str | None
      service_date: date | None
      schema_valid: bool
      validation_errors: list[str]
  ```
- **Extraction:** Structured output via Claude/Gemini vision

### 3.4 Policy Agent (RAG)
- **Setup:**
  1. Ingest policy PDFs with Docling
  2. Chunk semantically (by section/clause)
  3. Store in ChromaDB with embeddings
- **Input:** CPT codes from Claims Agent
- **Output:**
  ```python
  class PolicyOutput(AgentOutput):
      covered: bool
      coverage_percentage: float
      matching_clauses: list[str]
      exclusions: list[str]
  ```

### 3.5 Fraud Detection Agent
- **Input:** Patient history + current claim
- **Output:**
  ```python
  class FraudOutput(AgentOutput):
      fraud_score: float  # 0.0 - 1.0
      risk_level: Literal["LOW", "MEDIUM", "HIGH"]
      anomalies: list[str]
  ```
- **Checks:** Duplicate submissions, frequency anomalies, provider patterns

### 3.6 Orchestrator Agent
- **Input:** All upstream agent outputs
- **Decision Logic:**
  ```python
  if not kyc_output.kyc_passed:
      return Decision.REJECT, "KYC validation failed"
  if not claims_output.schema_valid:
      return Decision.REJECT, "Invalid claim schema"
  if not policy_output.covered:
      return Decision.REJECT, "Procedure not covered"
  if fraud_output.fraud_score >= 0.3:
      return Decision.ESCALATE, "High fraud risk"
  if any(o.confidence < 0.6 for o in agent_outputs):
      return Decision.ESCALATE, "Low confidence"
  return Decision.APPROVE, "All checks passed"
  ```

---

## Phase 4: LangGraph Pipeline

### 4.1 Graph Definition
```python
from langgraph.graph import StateGraph, END

def build_pipeline() -> StateGraph:
    graph = StateGraph(PipelineState)
    
    # Nodes
    graph.add_node("classify", classifier_node)
    graph.add_node("kyc", kyc_node)
    graph.add_node("claims", claims_node)
    graph.add_node("policy", policy_node)
    graph.add_node("fraud", fraud_node)
    graph.add_node("orchestrate", orchestrator_node)
    
    # Edges
    graph.set_entry_point("classify")
    graph.add_conditional_edges(
        "classify",
        route_by_doc_type,
        {
            "kyc_path": "kyc",
            "claims_path": "claims",
            "unknown": "orchestrate",
        }
    )
    # Parallel execution for KYC, Claims, Policy
    graph.add_edge("kyc", "fraud")
    graph.add_edge("claims", "policy")
    graph.add_edge("policy", "fraud")
    graph.add_edge("fraud", "orchestrate")
    graph.add_edge("orchestrate", END)
    
    return graph.compile()
```

---

## Phase 5: FastAPI Backend

### 5.1 Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/cases` | Upload document, create case |
| GET | `/api/cases` | List cases (filterable) |
| GET | `/api/cases/{id}` | Get case detail |
| GET | `/api/cases/{id}/report` | Download PDF audit report |
| GET | `/api/cases/{id}/image` | Get uploaded document image |
| PATCH | `/api/cases/{id}/override` | Human override decision |
| GET | `/api/cases/escalated` | Get review queue |
| GET | `/api/cases/stats` | Get case statistics |
| GET | `/api/analytics/calibration` | Get calibration data for charts |
| POST | `/api/policies/index` | Index policy PDFs for RAG |
| GET | `/api/health` | Health check |

### 5.2 Case Upload Flow
```python
@router.post("/cases")
async def create_case(file: UploadFile):
    case_id = str(uuid4())
    image_bytes = await file.read()
    
    # Save to storage
    save_document(case_id, image_bytes)
    
    # Run pipeline
    result = await pipeline.ainvoke({
        "case_id": case_id,
        "image_bytes": image_bytes,
    })
    
    # Persist result
    save_case(case_id, result)
    
    return {"case_id": case_id, "decision": result["final_decision"]}
```

---

## Phase 6: Next.js Frontend

### 6.1 Pages
- `/` — Dashboard with case list and PDF download links
- `/cases/[id]` — Case detail view with all agent outputs
- `/review` — Human review queue (escalated only) with override capability
- `/analytics` — Confidence calibration curves, ECE metrics, accuracy stats

### 6.2 Components
- `CaseTable` — Sortable, filterable case list with PDF report links
- `StatusBadge` — Processing/Approved/Rejected/Escalated
- `DocumentViewer` — Image viewer with zoom/pan
- `AgentOutputPanel` — Collapsible per-agent results
- `DecisionPanel` — Final decision with justification
- `OverrideForm` — Human override with comment
- `CalibrationChart` — SVG calibration curve visualization
- `StatCard` — Summary statistics display

---

## Phase 7: Testing & Evaluation

### 7.1 Test Dataset
Create ground-truth labels for 20+ documents:
```json
{
  "image": "claim_001.png",
  "expected_doc_type": "Claim Forms",
  "expected_decision": "APPROVE",
  "claim_amount": 1500.00,
  "icd_codes": ["J06.9"],
  "cpt_codes": ["99213"]
}
```

### 7.2 Evaluation Metrics
- Classification accuracy (target: 95%)
- Extraction completeness (all required fields)
- Decision correctness (target: 60% minimum)

---

## Implementation Order

| Week | Tasks |
|------|-------|
| 1 | Phase 1-2: Setup, models, state |
| 1 | Phase 3.1: Classifier agent |
| 2 | Phase 3.2-3.3: KYC + Claims agents |
| 2 | Phase 3.4: Policy RAG setup |
| 3 | Phase 3.5-3.6: Fraud + Orchestrator |
| 3 | Phase 4: LangGraph integration |
| 4 | Phase 5: FastAPI backend |
| 4 | Phase 6: Next.js frontend |
| 5 | Phase 7: Testing, evaluation, polish |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Rate limits (free tier) | Retry with backoff, delay between calls |
| Low classification accuracy | Improve prompts, add few-shot examples |
| RAG retrieval quality | Tune chunk size, test different embeddings |
| Vision model cost | Use Gemini Flash for dev, Claude for eval |

---

## Files to Create First

1. `pyproject.toml` — Dependencies
2. `app/config.py` — Settings
3. `app/models/document.py` — Core schemas
4. `app/models/agent_outputs.py` — Agent response types
5. `app/agents/base.py` — Base agent with retry logic
6. `app/agents/classifier.py` — First agent to implement

---

## Bonus Features (Implemented)

| Feature | Files | Description |
|---------|-------|-------------|
| Multi-language OCR | `app/agents/classifier.py`, `app/agents/claims.py` | EasyOCR supports English, Hindi, Spanish |
| LangSmith Tracing | `app/pipeline/graph.py` | Full observability of agent calls |
| Calibration CLI | `scripts/calibration_plot.py` | Generate calibration curves with ground truth |
| Calibration UI | `frontend/src/app/analytics/page.tsx` | Interactive calibration dashboard |
| Calibration API | `app/api/routes.py` | `GET /api/analytics/calibration` endpoint |
| PDF Audit Export | `app/api/pdf_export.py` | Generate PDF reports per case |
| PDF Download UI | `frontend/src/components/CaseTable.tsx` | PDF link in Dashboard table |
