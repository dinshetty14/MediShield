"""Policy retriever using ChromaDB."""

from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import get_settings
from app.models.agent_outputs import PolicyClause

from .cpt_mapping import get_categories_for_codes
from .ingestion import ingest_all_policies, ingest_policy_pdf


class PolicyRetriever:
    """Retrieves relevant policy clauses from ChromaDB."""

    def __init__(self, persist_dir: str | None = None):
        settings = get_settings()
        self.persist_dir = persist_dir or settings.chroma_persist_dir

        # Initialize ChromaDB client
        self._client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

        self._collection = self._client.get_or_create_collection(
            name="policy_documents",
            metadata={"hnsw:space": "cosine"},
        )

    def index_policies(self, policies_dir: str | Path | None = None) -> int:
        """Index all policies from the policies directory.

        Args:
            policies_dir: Optional path to policies directory

        Returns:
            Number of chunks indexed
        """
        chunks = ingest_all_policies(policies_dir)

        if not chunks:
            return 0

        # Prepare data for ChromaDB
        ids = [c["id"] for c in chunks]
        documents = [c["text"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]

        # Add to collection (upsert to handle re-indexing)
        self._collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

        return len(chunks)

    def index_single_pdf(self, pdf_path: str | Path) -> int:
        """Index a single policy PDF via Docling.

        Args:
            pdf_path: Path to the policy PDF file

        Returns:
            Number of chunks indexed
        """
        chunks = ingest_policy_pdf(pdf_path)

        if not chunks:
            return 0

        # Prepare data for ChromaDB
        ids = [c["id"] for c in chunks]
        documents = [c["text"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]

        # Add to collection (upsert to handle re-indexing)
        self._collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

        print(f"  [PolicyRetriever] Indexed {len(chunks)} chunks from {pdf_path}")
        return len(chunks)

    def retrieve(
        self,
        query: str,
        n_results: int = 5,
        filter_policy: str | None = None,
        filter_categories: list[str] | None = None,
    ) -> list[PolicyClause]:
        """Retrieve relevant policy clauses.

        Args:
            query: Semantic search query (diagnosis description, procedure name)
            n_results: Number of results to return
            filter_policy: Optional policy name to filter by
            filter_categories: Optional list of coverage categories to filter by

        Returns:
            List of PolicyClause objects
        """
        # Build where filter for metadata
        where_filter = None
        where_conditions = []

        if filter_policy:
            where_conditions.append({"policy_name": filter_policy})

        if filter_categories:
            # Filter chunks that contain any of the specified categories
            # Categories are stored as comma-separated string in metadata
            category_filters = [
                {"categories": {"$contains": cat}}
                for cat in filter_categories
            ]
            if len(category_filters) == 1:
                where_conditions.append(category_filters[0])
            elif len(category_filters) > 1:
                where_conditions.append({"$or": category_filters})

        if len(where_conditions) == 1:
            where_filter = where_conditions[0]
        elif len(where_conditions) > 1:
            where_filter = {"$and": where_conditions}

        results = self._collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        clauses = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else 1.0

                # Convert distance to relevance score (cosine distance -> similarity)
                relevance_score = 1.0 - distance

                clauses.append(PolicyClause(
                    text=doc,
                    section=metadata.get("section"),
                    relevance_score=max(0.0, min(1.0, relevance_score)),
                ))

        return clauses

    def retrieve_for_codes(
        self,
        icd_codes: list[str],
        cpt_codes: list[str],
        diagnosis: str | None = None,
        procedure_description: str | None = None,
        n_results: int = 5,
    ) -> list[PolicyClause]:
        """Retrieve policy clauses relevant to medical codes.

        Approach (per assignment clarification):
        1. Map CPT/ICD codes to coverage categories (metadata filter)
        2. Semantic search on diagnosis/procedure description (not codes)

        Args:
            icd_codes: List of ICD-10 diagnosis codes (for category mapping)
            cpt_codes: List of CPT procedure codes (for category mapping)
            diagnosis: Diagnosis description (for semantic search)
            procedure_description: Procedure description (for semantic search)
            n_results: Number of results to return

        Returns:
            List of PolicyClause objects
        """
        # Step 1: Map codes to coverage categories for metadata filtering
        categories = get_categories_for_codes(cpt_codes, icd_codes)

        if categories:
            print(f"  [PolicyRetriever] Filtering by categories: {categories}")

        # Step 2: Build semantic search query from description (NOT codes)
        query_parts = []

        if diagnosis:
            query_parts.append(diagnosis)

        if procedure_description:
            query_parts.append(procedure_description)

        # If no description available, use a generic query
        if not query_parts:
            query_parts.append("medical procedure coverage benefits policy")

        query = " ".join(query_parts)
        print(f"  [PolicyRetriever] Semantic query: {query[:80]}...")

        # Step 3: Retrieve with category filter + semantic search
        return self.retrieve(
            query=query,
            n_results=n_results,
            filter_categories=categories if categories else None,
        )

    def get_collection_count(self) -> int:
        """Return the number of documents in the collection."""
        return self._collection.count()

    def clear(self) -> None:
        """Clear all documents from the collection."""
        self._client.delete_collection("policy_documents")
        self._collection = self._client.get_or_create_collection(
            name="policy_documents",
            metadata={"hnsw:space": "cosine"},
        )
