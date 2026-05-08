"""Policy retriever using ChromaDB."""

from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import get_settings
from app.models.agent_outputs import PolicyClause

from .ingestion import ingest_all_policies


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

    def retrieve(
        self,
        query: str,
        n_results: int = 5,
        filter_policy: str | None = None,
    ) -> list[PolicyClause]:
        """Retrieve relevant policy clauses.

        Args:
            query: Search query (e.g., procedure description or CPT codes)
            n_results: Number of results to return
            filter_policy: Optional policy name to filter by

        Returns:
            List of PolicyClause objects
        """
        where_filter = None
        if filter_policy:
            where_filter = {"policy_name": filter_policy}

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
        n_results: int = 5,
    ) -> list[PolicyClause]:
        """Retrieve policy clauses relevant to medical codes.

        Args:
            icd_codes: List of ICD-10 diagnosis codes
            cpt_codes: List of CPT procedure codes
            diagnosis: Optional diagnosis description
            n_results: Number of results to return

        Returns:
            List of PolicyClause objects
        """
        # Build search query from codes and diagnosis
        query_parts = []

        if diagnosis:
            query_parts.append(diagnosis)

        if icd_codes:
            query_parts.append(f"ICD-10 codes: {', '.join(icd_codes)}")

        if cpt_codes:
            query_parts.append(f"CPT codes: {', '.join(cpt_codes)}")

        if not query_parts:
            query_parts.append("medical procedure coverage policy")

        query = " ".join(query_parts)
        return self.retrieve(query, n_results)

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
