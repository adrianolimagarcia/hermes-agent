"""Hybrid Knowledge Router (OKF + RAG/GraphRAG) for HAOS.

Combines deterministic, offline-first OKF knowledge bundles with
probabilistic relational/vector GraphRAG retrieval.
Works seamlessly offline (local files, local vault, local index).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from hermes.platform.memory.okf import OKFStore
from hermes.platform.memory.graphrag import GraphRAGClient


class HybridKnowledgeRouter:
    """Intelligent router directing queries to deterministic OKF first, with RAG fallback."""

    def __init__(self, okf_dir: Path, graphrag_dir: Optional[Path] = None):
        self.okf_store = OKFStore(okf_dir)
        self.graphrag_client = (
            GraphRAGClient(index_dir=str(graphrag_dir)) if graphrag_dir else None
        )

    def query(self, query_str: str, mode: str = "hybrid") -> Dict[str, Any]:
        """Perform routed query.

        1. Deterministic path: Check OKF store first.
        2. Probabilistic path: Fallback to GraphRAG if no deterministic match is found.
        """
        # Step 1: Deterministic lookup via OKF
        okf_doc = self.okf_store.find_deterministic(query_str)
        if okf_doc:
            return {
                "source": "OKF_CANONICAL",
                "deterministic": True,
                "found": True,
                "doc": okf_doc.to_dict(),
                "content": f"[SOURCE: CANONICAL KNOWLEDGE (OKF)]\nTitle: {okf_doc.title}\n\n{okf_doc.body}",
            }

        # If deterministic match not found and mode is hybrid, attempt RAG
        if mode in ("hybrid", "rag") and self.graphrag_client and self.graphrag_client.available():
            try:
                rag_results = self.graphrag_client.query_global(query_str)
                return {
                    "source": "RAG_PROBABILISTIC",
                    "deterministic": False,
                    "found": bool(rag_results),
                    "results": rag_results,
                    "content": f"[SOURCE: PROBABILISTIC SEARCH (GraphRAG)]\n{rag_results}",
                }
            except Exception as exc:
                return {
                    "source": "RAG_ERROR",
                    "deterministic": False,
                    "found": False,
                    "error": str(exc),
                }

        # Step 3: Broader search in OKF as second-tier fallback before failing
        broader_matches = self.okf_store.search_all(query_str)
        if broader_matches:
            top_match = broader_matches[0]
            return {
                "source": "OKF_BROAD_MATCH",
                "deterministic": True,
                "found": True,
                "doc": top_match.to_dict(),
                "content": f"[SOURCE: CANONICAL KNOWLEDGE (OKF - Fuzzy)]\nTitle: {top_match.title}\n\n{top_match.body}",
            }

        return {
            "source": "NONE",
            "deterministic": True,
            "found": False,
            "message": f"No authoritative or probabilistic knowledge found for query: {query_str!r}",
        }
