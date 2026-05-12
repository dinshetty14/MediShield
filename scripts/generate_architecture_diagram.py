#!/usr/bin/env python
"""
Generate MediShield architecture diagram using the 'diagrams' library.

Requirements:
    pip install diagrams

Usage:
    python scripts/generate_architecture_diagram.py

Output:
    docs/medishield_architecture.png
"""

from diagrams import Cluster, Diagram, Edge
from diagrams.custom import Custom
from diagrams.onprem.client import Users
from diagrams.onprem.compute import Server
from diagrams.onprem.database import PostgreSQL
from diagrams.onprem.inmemory import Redis
from diagrams.onprem.mlops import Mlflow
from diagrams.onprem.network import Nginx
from diagrams.programming.framework import FastAPI, React
from diagrams.programming.language import Python

# Note: Some icons may not be available, using alternatives

with Diagram(
    "MediShield - Multi-Agent Document Intelligence Pipeline",
    filename="docs/medishield_architecture",
    show=False,
    direction="LR",
    graph_attr={
        "fontsize": "20",
        "bgcolor": "white",
        "pad": "0.5",
    },
):
    # User/Upload
    user = Users("Operations\nTeam")

    with Cluster("1. Document Ingestion"):
        api = FastAPI("FastAPI\nUpload API")
        storage = PostgreSQL("Object\nStorage")

    with Cluster("2. Classifier Agent (3-Stage)"):
        classifier = Python("Regex → OCR → LLM\n(Gemini Vision)")

    with Cluster("3. Smart Routing (LangGraph)"):
        router = Server("Route by\ndoc_type")

    with Cluster("4. Agent Execution Pipeline"):
        with Cluster("KYC Path"):
            kyc = Python("KYC Agent\n(Vision LLM)")

        with Cluster("Claims Path"):
            claims = Python("Claims Agent\n(OCR + LLM)")
            policy = Python("Policy Agent\n(RAG)")

        with Cluster("Policy Ingestion"):
            ingest = Python("Docling\nPDF Parser")

        fraud = Python("Fraud Agent\n(Rule-based)")

    with Cluster("5. Orchestrator"):
        orchestrator = Mlflow("Decision:\nAPPROVE/REJECT\n/ESCALATE")

    with Cluster("6. Case Management UI"):
        ui = React("Next.js\nDashboard")

    with Cluster("Data Layer"):
        sqlite = PostgreSQL("SQLite\nmedishield.db")
        chromadb = Redis("ChromaDB\npolicy vectors")

    # Connections
    user >> api >> storage
    api >> classifier >> router

    router >> Edge(label="CLAIM/BILL") >> claims
    router >> Edge(label="KYC") >> kyc
    router >> Edge(label="POLICY_DOC") >> ingest

    claims >> policy >> fraud
    kyc >> fraud
    fraud >> orchestrator

    ingest >> chromadb
    policy >> Edge(style="dashed") >> chromadb

    orchestrator >> sqlite >> ui >> user


print("Diagram generated: docs/medishield_architecture.png")
