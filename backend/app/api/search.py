"""
Hybrid search endpoint — POST /api/search
"""
from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.retrieval import get_retrieval_service

router = APIRouter(prefix="/api/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language search query")
    project_id: Optional[str] = Field(None, description="Restrict to a specific project ID")
    doc_type: Optional[str] = Field(
        None,
        description="Filter by doc type: resume, jd, report, interview, job_request, client_report",
    )
    top_k: int = Field(10, ge=1, le=50, description="Number of results to return")


class SearchResult(BaseModel):
    chunk_id: str
    text: str
    metadata: dict[str, Any]
    bm25_score: float
    vector_score: float
    combined_score: float


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[SearchResult]


@router.post("", response_model=SearchResponse)
def search(body: SearchRequest):
    """
    Hybrid BM25 + vector search with Reciprocal Rank Fusion.
    Optionally filter by project_id and/or doc_type.
    """
    svc = get_retrieval_service()
    results = svc.hybrid_search(
        query=body.query,
        project_id=body.project_id,
        doc_type=body.doc_type,
        top_k=body.top_k,
    )
    return SearchResponse(query=body.query, total=len(results), results=results)
