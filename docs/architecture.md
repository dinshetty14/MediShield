# MediShield Architecture Diagram

## Mermaid Diagram (renders in GitHub/VS Code)

```mermaid
flowchart TB
    subgraph Upload["1. Document Upload"]
        API[FastAPI Upload API]
        Storage[(Object Storage<br/>uploads/)]
    end

    subgraph Classifier["2. Classifier Agent"]
        direction TB
        C1[Stage 1: Regex<br/>Filename patterns]
        C2[Stage 2: OCR<br/>EasyOCR keywords]
        C3[Stage 3: LLM<br/>Gemini Vision]
        C1 --> C2 --> C3
    end

    subgraph Routing["3. Smart Routing"]
        Router{Route by<br/>doc_type}
    end

    subgraph Agents["4. Agent Execution Pipeline"]
        direction LR
        subgraph KYCBox["KYC Agent"]
            KYC[Identity validation<br/>Expiry checks<br/>Tamper detection]
        end
        subgraph ClaimsBox["Claims Agent"]
            Claims[Extract amounts<br/>ICD-10 codes<br/>CPT codes<br/>Provider info]
        end
        subgraph PolicyBox["Policy Agent"]
            Policy[Query ChromaDB<br/>Category filtering<br/>Coverage decision]
        end
        subgraph FraudBox["Fraud Agent"]
            Fraud[Duplicate detection<br/>Amount anomaly<br/>Frequency check]
        end
        subgraph IngestBox["Policy Ingestion"]
            Ingest[Docling PDF parse<br/>Chunk & embed<br/>Store in ChromaDB]
        end
    end

    subgraph Orchestrator["5. Orchestrator Agent"]
        Orch[Aggregate results<br/>Apply decision rules<br/>APPROVE/REJECT/ESCALATE]
    end

    subgraph UI["6. Case Management UI"]
        Dashboard[Dashboard<br/>PDF Reports]
        CaseDetail[Case Details]
        ReviewQueue[Human Review]
        Analytics[Analytics<br/>Calibration]
    end

    subgraph DataLayer["Data & Knowledge Layer"]
        SQLite[(SQLite<br/>medishield.db<br/>cases table)]
        ChromaDB[(ChromaDB<br/>chroma_db/<br/>policy embeddings)]
    end

    %% Flow
    API --> Storage
    API --> Classifier
    Classifier --> Router

    Router -->|CLAIM_FORM<br/>PATIENT_BILL<br/>PRESCRIPTION| Claims
    Router -->|KYC_DOCUMENT| KYC
    Router -->|POLICY_DOCUMENT| Ingest
    Router -->|UNKNOWN| Orch

    Claims --> Policy
    Policy --> Fraud
    KYC --> Fraud
    Fraud --> Orch
    Ingest --> ChromaDB

    Orch --> SQLite
    SQLite --> UI
    Policy <--> ChromaDB

    %% Styling
    classDef primary fill:#4F46E5,stroke:#3730A3,color:#fff
    classDef secondary fill:#10B981,stroke:#059669,color:#fff
    classDef storage fill:#F59E0B,stroke:#D97706,color:#fff
    classDef decision fill:#EF4444,stroke:#DC2626,color:#fff

    class API,Classifier primary
    class KYC,Claims,Policy,Fraud,Ingest secondary
    class SQLite,ChromaDB,Storage storage
    class Router,Orch decision
```

## Pipeline State Machine

```mermaid
stateDiagram-v2
    [*] --> RECEIVED: Document Upload
    RECEIVED --> CLASSIFIED: Classifier Agent
    
    CLASSIFIED --> KYC: ID_DOCUMENT
    CLASSIFIED --> EXTRACTION: CLAIM_FORM/BILL/RX
    CLASSIFIED --> POLICY_INGESTION: POLICY_DOCUMENT
    CLASSIFIED --> DECIDED: UNKNOWN
    
    KYC --> FRAUD_CHECK
    EXTRACTION --> FRAUD_CHECK
    POLICY_INGESTION --> [*]: Indexed in ChromaDB
    
    FRAUD_CHECK --> DECIDED: Orchestrator
    DECIDED --> [*]

    note right of EXTRACTION
        Claims Agent → Policy Agent
        (Sequential)
    end note

    note right of DECIDED
        APPROVE / REJECT / ESCALATE
    end note
```

## Routing Table

| Document Type | Flow |
|--------------|------|
| `CLAIM_FORM` | Classifier → Claims → Policy → Fraud → Orchestrator |
| `PATIENT_BILL` | Classifier → Claims → Policy → Fraud → Orchestrator |
| `PRESCRIPTION` | Classifier → Claims → Policy → Fraud → Orchestrator |
| `MEDICAL_REPORT` | Classifier → Claims → Policy → Fraud → Orchestrator |
| `KYC_DOCUMENT` | Classifier → KYC → Fraud → Orchestrator |
| `POLICY_DOCUMENT` | Classifier → Policy Ingestion → END |
| `UNKNOWN` | Classifier → Orchestrator (reject) |

## Tech Stack

| Component | Technology |
|-----------|------------|
| Orchestration | LangGraph |
| Vision LLM | Gemini Flash |
| OCR | EasyOCR (English, Hindi, Spanish) |
| PDF Parsing | Docling |
| Vector DB | ChromaDB |
| Relational DB | SQLite |
| Backend API | FastAPI |
| Frontend | Next.js + Tailwind |
| Observability | LangSmith Tracing |
| Reports | ReportLab PDF Export |

## Decision Logic

```
APPROVE: KYC passed + claim valid + covered + fraud_score < 0.3
REJECT:  KYC failed OR not covered OR schema invalid
ESCALATE: fraud_score >= 0.3 OR any confidence < 0.6 OR duplicate detected
```

## Bonus Features

| Feature | Description |
|---------|-------------|
| Multi-language OCR | EasyOCR supports English, Hindi, Spanish documents |
| LangSmith Tracing | Full observability of agent calls, latency, token usage |
| Confidence Calibration | CLI script + UI Analytics page with calibration curves and ECE metrics |
| PDF Audit Export | Download case reports as PDF via UI button or `/api/cases/{id}/report` |

## UI Pages

| Page | Path | Description |
|------|------|-------------|
| Dashboard | `/` | Upload documents, view cases, download PDF reports |
| Case Detail | `/cases/[id]` | Full case details with agent outputs |
| Review Queue | `/review` | Escalated cases with override capability |
| Analytics | `/analytics` | Confidence calibration curves, ECE, accuracy metrics |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/cases` | Upload document, trigger pipeline |
| GET | `/api/cases` | List cases with filters |
| GET | `/api/cases/{id}` | Get case detail with agent outputs |
| GET | `/api/cases/{id}/report` | Download PDF audit report |
| GET | `/api/cases/{id}/image` | Get uploaded document image |
| PATCH | `/api/cases/{id}/override` | Override decision (escalated only) |
| GET | `/api/cases/escalated` | Get review queue |
| GET | `/api/cases/stats` | Get case statistics |
| GET | `/api/analytics/calibration` | Get calibration data for charts |
| POST | `/api/policies/index` | Index policy PDFs for RAG |
