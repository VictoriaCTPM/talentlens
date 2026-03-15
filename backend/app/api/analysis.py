"""
AI Analysis endpoints — /api/analysis/*
"""
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.database import AnalysisResult, Document, get_db
from app.schemas.schemas import AnalysisResultResponse
from app.services.analysis import data_sufficiency_check, get_analysis_engine

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


# ── Request bodies ────────────────────────────────────────────────────────────

class TalentBriefRequest(BaseModel):
    document_id: int


class HistoricalMatchRequest(BaseModel):
    document_id: int


class LevelAdvisorRequest(BaseModel):
    document_id: int


class CandidateScoreRequest(BaseModel):
    resume_document_id: int
    jd_document_id: int


class JDRealityCheckRequest(BaseModel):
    document_id: int


class PositionIntelligenceRequest(BaseModel):
    jd_document_id: int


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_project(document_id: int, db: Session) -> int:
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    if doc.status != "processed":
        raise HTTPException(
            status_code=422,
            detail=f"Document {document_id} is not ready (status={doc.status}). Wait for processing to complete.",
        )
    return doc.project_id


def _check_sufficiency(project_id: int, mode: str) -> None:
    check = data_sufficiency_check(project_id, mode)
    if not check["can_run"]:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Insufficient data to run this analysis",
                "missing": check["missing"],
                "data_quality": check["data_quality"],
            },
        )


# ── Mode A — Talent Brief ─────────────────────────────────────────────────────

@router.post("/talent-brief")
async def talent_brief(
    body: TalentBriefRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Analyze a JD and return a Talent Brief: required skills, search tips,
    historical insights, pitfalls, and estimated time-to-fill.
    """
    project_id = _resolve_project(body.document_id, db)
    _check_sufficiency(project_id, "A")

    engine = get_analysis_engine()
    return await engine.talent_brief(body.document_id)


# ── Mode B — Historical Match ─────────────────────────────────────────────────

@router.post("/historical-match")
async def historical_match(
    body: HistoricalMatchRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Find similar past positions and extract success/failure patterns.
    """
    project_id = _resolve_project(body.document_id, db)
    _check_sufficiency(project_id, "B")

    engine = get_analysis_engine()
    return await engine.historical_match(body.document_id)


# ── Mode C — Level Advisor ────────────────────────────────────────────────────

@router.post("/level-advisor")
async def level_advisor(
    body: LevelAdvisorRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Recommend the right seniority level based on historical evidence.
    """
    project_id = _resolve_project(body.document_id, db)
    _check_sufficiency(project_id, "C")

    engine = get_analysis_engine()
    return await engine.level_advisor(body.document_id)


# ── Position Intelligence (A+B+C combined) ────────────────────────────────────

@router.post("/position-intelligence")
async def position_intelligence(
    body: PositionIntelligenceRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Run Modes A+B+C in a single LLM call (or return cached results if run within the last hour).
    Returns talent_brief, historical_match, and level_advisor together.
    Prefer this endpoint over calling A/B/C separately — ~67% fewer tokens.
    """
    project_id = _resolve_project(body.jd_document_id, db)
    _check_sufficiency(project_id, "A")  # A has the loosest requirements of the three

    engine = get_analysis_engine()
    return await engine.position_intelligence(body.jd_document_id)


# ── Mode D — Candidate Scorer ─────────────────────────────────────────────────

@router.post("/candidate-score")
async def candidate_score(
    body: CandidateScoreRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Score a candidate (resume) against a JD, with historical comparison.
    Returns overall score 0-100, skill breakdown, and verdict.
    """
    project_id = _resolve_project(body.jd_document_id, db)
    _resolve_project(body.resume_document_id, db)  # validate resume exists
    _check_sufficiency(project_id, "D")

    engine = get_analysis_engine()
    return await engine.candidate_score(body.resume_document_id, body.jd_document_id)


# ── Mode E — JD Reality Check ─────────────────────────────────────────────────

@router.post("/jd-reality-check")
async def jd_reality_check(
    body: JDRealityCheckRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Audit a JD against the current team composition and weekly reports.
    Checks: are the required skills already on the team? Does the JD match what the team actually does?
    Is this hire actually necessary?
    """
    project_id = _resolve_project(body.document_id, db)
    _check_sufficiency(project_id, "E")

    engine = get_analysis_engine()
    return await engine.jd_reality_check(body.document_id)


# ── Data sufficiency check ────────────────────────────────────────────────────

@router.get("/sufficiency/{project_id}/{mode}")
def check_sufficiency(project_id: int, mode: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Check if a project has enough data to run a given analysis mode (A/B/C/D).
    Use this before triggering analysis to show the user what's missing.
    """
    if mode.upper() not in ("A", "B", "C", "D", "E"):
        raise HTTPException(status_code=400, detail="Mode must be A, B, C, D, or E")
    return data_sufficiency_check(project_id, mode.upper())


# ── Results history ───────────────────────────────────────────────────────────

@router.get("/results/{project_id}", response_model=list[AnalysisResultResponse])
def get_results(project_id: int, db: Session = Depends(get_db)) -> list[AnalysisResult]:
    """Return all past analysis results for a project, newest first."""
    return (
        db.query(AnalysisResult)
        .filter_by(project_id=project_id)
        .order_by(AnalysisResult.created_at.desc())
        .all()
    )


@router.get("/results/detail/{result_id}", response_model=AnalysisResultResponse)
def get_analysis_result(result_id: int, db: Session = Depends(get_db)) -> AnalysisResult:
    """Return a single analysis result by ID."""
    ar = db.get(AnalysisResult, result_id)
    if not ar:
        raise HTTPException(status_code=404, detail="Analysis result not found")
    return ar
