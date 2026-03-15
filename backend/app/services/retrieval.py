"""
Hybrid retrieval: BM25 + vector cosine similarity merged via Reciprocal Rank Fusion.
Follows DEC-006: BM25 keyword + vector, RRF merge, metadata pre-filters.
"""
import logging
from typing import Any

from rank_bm25 import BM25Okapi

from app.services.embeddings import get_embedding_service
from app.services.vector_store import get_vector_store

logger = logging.getLogger(__name__)

_RRF_K = 60  # standard RRF constant; higher = smoother rank blending


def _build_where_filter(
    project_id: str | None,
    doc_type: str | None,
) -> dict | None:
    """Build a ChromaDB metadata filter from optional fields."""
    filters = []
    if project_id:
        filters.append({"project_id": str(project_id)})
    if doc_type:
        filters.append({"doc_type": doc_type})

    if not filters:
        return None
    if len(filters) == 1:
        return filters[0]
    return {"$and": filters}


class RetrievalService:
    """BM25 + vector hybrid search with Reciprocal Rank Fusion."""

    def hybrid_search(
        self,
        query: str,
        project_id: str | None = None,
        doc_type: str | None = None,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search across stored document chunks using both keyword and semantic signals.

        Args:
            query:      Natural language search query.
            project_id: Restrict to a specific project (optional).
            doc_type:   Restrict to a doc type, e.g. "resume", "jd" (optional).
            top_k:      Number of results to return.

        Returns:
            List of dicts sorted by combined RRF score:
                chunk_id, text, metadata, bm25_score, vector_score, combined_score
        """
        where_filter = _build_where_filter(project_id, doc_type)

        # ── 1. Fetch entire filtered corpus for BM25 ─────────────────────────
        vs = get_vector_store()
        corpus = vs.get_all(where_filter=where_filter)

        if not corpus:
            logger.debug("hybrid_search: empty corpus for filter %s", where_filter)
            return []

        n = len(corpus)

        # ── 2. BM25 keyword search ────────────────────────────────────────────
        tokenized_corpus = [doc["text"].lower().split() for doc in corpus]
        bm25 = BM25Okapi(tokenized_corpus)
        bm25_scores_raw = bm25.get_scores(query.lower().split())

        # Map chunk_id → BM25 rank (0 = best) and raw score
        bm25_order = sorted(range(n), key=lambda i: bm25_scores_raw[i], reverse=True)
        bm25_rank: dict[str, int] = {corpus[i]["id"]: rank for rank, i in enumerate(bm25_order)}
        bm25_score_map: dict[str, float] = {
            corpus[i]["id"]: float(bm25_scores_raw[i]) for i in range(n)
        }

        # ── 3. Vector similarity search ───────────────────────────────────────
        embed_svc = get_embedding_service()
        query_embedding = embed_svc.embed_text(query)

        vector_results = vs.search(
            query_embedding=query_embedding,
            n_results=min(top_k * 3, n),  # over-fetch for better RRF coverage
            where_filter=where_filter,
        )

        vector_rank: dict[str, int] = {}
        vector_score_map: dict[str, float] = {}
        for rank, result in enumerate(vector_results):
            vector_rank[result["id"]] = rank
            vector_score_map[result["id"]] = result["score"]

        # ── 4. Reciprocal Rank Fusion ─────────────────────────────────────────
        all_ids = {doc["id"] for doc in corpus}
        rrf_scores: dict[str, float] = {}

        for chunk_id in all_ids:
            br = bm25_rank.get(chunk_id, n)      # worst rank if missing
            vr = vector_rank.get(chunk_id, n)
            rrf_scores[chunk_id] = 1 / (_RRF_K + br + 1) + 1 / (_RRF_K + vr + 1)

        # ── 5. Sort and return top_k ──────────────────────────────────────────
        top_ids = sorted(all_ids, key=lambda cid: rrf_scores[cid], reverse=True)[:top_k]

        corpus_by_id = {doc["id"]: doc for doc in corpus}

        results = []
        for chunk_id in top_ids:
            doc = corpus_by_id[chunk_id]
            results.append({
                "chunk_id": chunk_id,
                "text": doc["text"],
                "metadata": doc["metadata"],
                "bm25_score": round(bm25_score_map.get(chunk_id, 0.0), 4),
                "vector_score": round(vector_score_map.get(chunk_id, 0.0), 4),
                "combined_score": round(rrf_scores[chunk_id], 6),
            })

        logger.debug(
            "hybrid_search '%s' → %d results (corpus=%d, filter=%s)",
            query, len(results), n, where_filter,
        )
        return results

    def get_context_for_analysis(
        self,
        query: str,
        project_id: str,
        doc_types: list[str] | None = None,
        max_tokens: int = 8000,
    ) -> str:
        """
        Retrieve the most relevant chunks and format them as a grounded context
        string with source citations for AI analysis prompts.

        Args:
            query:      The analysis question or job description text.
            project_id: Restrict to this project's documents.
            doc_types:  If set, fetch from each doc_type separately then merge.
            max_tokens: Approximate token budget (~4 chars per token).

        Returns:
            Formatted string with cited chunks, ready to inject into LLM prompt.
        """
        max_chars = max_tokens * 4

        if doc_types:
            # Search each type separately, deduplicate, then re-rank by combined score
            all_results: list[dict[str, Any]] = []
            seen_ids: set[str] = set()
            for dt in doc_types:
                for r in self.hybrid_search(query, project_id=project_id, doc_type=dt, top_k=5):
                    if r["chunk_id"] not in seen_ids:
                        seen_ids.add(r["chunk_id"])
                        all_results.append(r)
                    else:
                        # Keep the higher-scoring version
                        for i, existing in enumerate(all_results):
                            if existing["chunk_id"] == r["chunk_id"] and r["combined_score"] > existing["combined_score"]:
                                all_results[i] = r
                                break
            all_results.sort(key=lambda r: r["combined_score"], reverse=True)
            results = all_results[:15]
        else:
            results = self.hybrid_search(query, project_id=project_id, top_k=15)

        if not results:
            return "No relevant documents found in this project."

        parts: list[str] = []
        total_chars = 0

        for i, r in enumerate(results, 1):
            meta = r["metadata"]
            person = meta.get("person_name") or ""
            section = meta.get("section") or ""
            dtype = meta.get("doc_type") or "unknown"
            citation = f"[Source {i} | {dtype}{' | ' + person if person else ''}{' | ' + section if section else ''}]"
            chunk = f"{citation}\n{r['text']}"

            if total_chars + len(chunk) > max_chars:
                break

            parts.append(chunk)
            total_chars += len(chunk)

        return "\n\n---\n\n".join(parts)


def get_retrieval_service() -> RetrievalService:
    """Singleton accessor."""
    return RetrievalService()
