"""
Candidates API — /api/positions/{position_id}/candidates and /api/candidates
"""
import hashlib
import logging
import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

logger = logging.getLogger(__name__)
from sqlalchemy.orm import Session

from app.models.database import (
    AnalysisResult, Candidate, CandidateEvent, Document, ExtractedData,
    Position, ProcessingJob, get_db,
)
from app.schemas.schemas import (
    CandidateEventResponse, CandidateList, CandidateResponse, CandidateUpdate,
)

router = APIRouter(tags=["candidates"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _compute_margin(candidate: Candidate, position_db: Position | None = None) -> dict:
    """Compute margin between client_rate and candidate_rate, normalized to monthly."""
    def to_monthly(rate, period):
        if rate is None:
            return None
        if period == "hourly":
            return rate * 160  # 40h/week * 4 weeks
        if period == "annual":
            return rate / 12
        return rate  # monthly (default)

    c_monthly = to_monthly(candidate.candidate_rate, candidate.candidate_rate_period)

    client_rate = None
    client_period = None
    if position_db:
        client_rate = position_db.client_rate
        client_period = position_db.client_rate_period
    cl_monthly = to_monthly(client_rate, client_period)

    if c_monthly is None and cl_monthly is None:
        return {"is_calculated": False, "missing": "both"}
    if c_monthly is None:
        return {"is_calculated": False, "missing": "candidate_rate"}
    if cl_monthly is None:
        return {"is_calculated": False, "missing": "client_rate"}

    margin_abs = cl_monthly - c_monthly
    margin_pct = (margin_abs / cl_monthly * 100) if cl_monthly else 0
    currency = candidate.candidate_rate_currency or "USD"

    return {
        "is_calculated": True,
        "client_rate_monthly": round(cl_monthly, 2),
        "candidate_rate_monthly": round(c_monthly, 2),
        "margin_absolute": round(margin_abs, 2),
        "margin_percentage": round(margin_pct, 1),
        "currency": currency,
    }


def _candidate_to_response(
    c: Candidate,
    analysis: AnalysisResult | None = None,
    include_resume: bool = False,
    db=None,
) -> CandidateResponse:
    skill_match_score = None
    scored_at = None
    if analysis and analysis.result_data:
        sm = analysis.result_data.get("skill_match", {})
        if isinstance(sm, dict):
            skill_match_score = sm.get("score")
        scored_at = analysis.created_at

    resume_extracted = None
    if include_resume and c.resume_document_id and db is not None:
        doc = db.get(Document, c.resume_document_id)
        if doc and doc.extracted_data:
            resume_extracted = doc.extracted_data[0].structured_data

    position_db = None
    if db is not None:
        position_db = db.get(Position, c.position_id)
    margin = _compute_margin(c, position_db)

    return CandidateResponse(
        id=c.id,
        position_id=c.position_id,
        name=c.name,
        email=c.email,
        resume_document_id=c.resume_document_id,
        status=c.status,
        ai_score=c.ai_score,
        ai_verdict=c.ai_verdict,
        ai_analysis_id=c.ai_analysis_id,
        notes=c.notes,
        created_at=c.created_at,
        updated_at=c.updated_at,
        phone=c.phone,
        years_of_experience=c.years_of_experience,
        salary_expectation=c.salary_expectation,
        location=c.location,
        availability=c.availability,
        recruiter_notes=c.recruiter_notes,
        interview_notes=c.interview_notes,
        client_feedback=c.client_feedback,
        rejection_reason=c.rejection_reason,
        tags=c.tags,
        candidate_rate=c.candidate_rate,
        candidate_rate_currency=c.candidate_rate_currency,
        candidate_rate_period=c.candidate_rate_period,
        skill_match_score=skill_match_score,
        scored_at=scored_at,
        resume_extracted=resume_extracted,
        margin=margin,
    )


def _extract_profile_from_resume(doc: Document) -> dict:
    """Pull profile fields out of extracted_data if available."""
    if not doc.extracted_data:
        return {}
    for ed in doc.extracted_data:
        data = ed.structured_data
        return {
            "name": data.get("full_name") or data.get("name"),
            "email": data.get("email"),
            "phone": data.get("phone"),
            "years_of_experience": data.get("years_of_experience"),
            "location": data.get("location"),
        }
    return {}


# ── Position-scoped endpoints ─────────────────────────────────────────────────

@router.post("/api/positions/{position_id}/candidates", response_model=CandidateResponse, status_code=201)
async def add_candidate(
    position_id: int,
    name: str = Form(default=""),
    email: str = Form(default=""),
    resume_document_id: int = Form(default=0),
    notes: str = Form(default=""),
    file: UploadFile = File(default=None),
    db: Session = Depends(get_db),
):
    pos = db.get(Position, position_id)
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")

    resolved_doc_id: int | None = resume_document_id if resume_document_id else None
    resolved_name = name or None
    resolved_email = email or None
    profile: dict = {}

    # ── If a file was uploaded, save & enqueue it ──────────────────────────────
    if file and file.filename:
        from app.config.settings import settings
        from app.services import job_queue

        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in {".pdf", ".doc", ".docx", ".txt"}:
            raise HTTPException(status_code=400, detail="Unsupported file type")

        content = await file.read()
        content_hash = hashlib.sha256(content).hexdigest()

        existing = db.query(Document).filter(Document.content_hash == content_hash).first()
        if existing:
            resolved_doc_id = existing.id
            profile = _extract_profile_from_resume(existing)
        else:
            safe_name = f"{uuid.uuid4().hex}{ext}"
            file_path = os.path.join(settings.UPLOAD_DIR, safe_name)
            os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(content)

            doc = Document(
                project_id=pos.project_id,
                filename=safe_name,
                original_filename=file.filename,
                file_path=file_path,
                file_type=ext.lstrip("."),
                doc_type="resume",
                file_size=len(content),
                status="queued",
                content_hash=content_hash,
            )
            db.add(doc)
            db.flush()

            job = ProcessingJob(
                document_id=doc.id,
                job_type="process_document",
                status="queued",
                progress=0,
            )
            db.add(job)
            db.commit()
            db.refresh(doc)
            await job_queue.enqueue(doc.id, job.id)
            resolved_doc_id = doc.id

    # ── Auto-fill from existing document ──────────────────────────────────────
    if resolved_doc_id and not profile:
        doc = db.get(Document, resolved_doc_id)
        if doc:
            profile = _extract_profile_from_resume(doc)
            if not profile.get("name") and not resolved_name:
                profile["name"] = os.path.splitext(doc.original_filename)[0]

    resolved_name = resolved_name or profile.get("name") or "Unknown Candidate"
    resolved_email = resolved_email or profile.get("email")

    candidate = Candidate(
        position_id=position_id,
        name=resolved_name,
        email=resolved_email,
        resume_document_id=resolved_doc_id,
        notes=notes or None,
        status="new",
        phone=profile.get("phone"),
        years_of_experience=profile.get("years_of_experience"),
        location=profile.get("location"),
    )
    db.add(candidate)
    db.flush()

    # Log creation event
    db.add(CandidateEvent(
        candidate_id=candidate.id,
        event_type="created",
        event_data={"name": candidate.name, "position_id": position_id},
    ))
    db.commit()
    db.refresh(candidate)
    return _candidate_to_response(candidate, db=db)


@router.get("/api/positions/{position_id}/candidates", response_model=CandidateList)
def list_candidates(position_id: int, db: Session = Depends(get_db)):
    pos = db.get(Position, position_id)
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")

    candidates = (
        db.query(Candidate)
        .filter(Candidate.position_id == position_id)
        .order_by(
            Candidate.ai_score.desc().nullslast(),
            Candidate.created_at.asc(),
        )
        .all()
    )
    items = []
    for c in candidates:
        analysis = db.get(AnalysisResult, c.ai_analysis_id) if c.ai_analysis_id else None
        items.append(_candidate_to_response(c, analysis, db=db))
    return CandidateList(items=items, total=len(items))


# ── Single candidate endpoints ────────────────────────────────────────────────

@router.get("/api/candidates/{candidate_id}/timeline", response_model=list[CandidateEventResponse])
def get_candidate_timeline(candidate_id: int, db: Session = Depends(get_db)):
    c = db.get(Candidate, candidate_id)
    if not c:
        raise HTTPException(status_code=404, detail="Candidate not found")
    events = (
        db.query(CandidateEvent)
        .filter(CandidateEvent.candidate_id == candidate_id)
        .order_by(CandidateEvent.created_at.desc())
        .all()
    )
    return events


@router.get("/api/candidates/{candidate_id}", response_model=CandidateResponse)
def get_candidate(candidate_id: int, db: Session = Depends(get_db)):
    c = db.get(Candidate, candidate_id)
    if not c:
        raise HTTPException(status_code=404, detail="Candidate not found")
    analysis = db.get(AnalysisResult, c.ai_analysis_id) if c.ai_analysis_id else None
    return _candidate_to_response(c, analysis, include_resume=True, db=db)


@router.put("/api/candidates/{candidate_id}", response_model=CandidateResponse)
def update_candidate(candidate_id: int, body: CandidateUpdate, db: Session = Depends(get_db)):
    c = db.get(Candidate, candidate_id)
    if not c:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if body.status is not None and body.status != c.status:
        db.add(CandidateEvent(
            candidate_id=c.id,
            event_type="status_change",
            event_data={"from": c.status, "to": body.status},
        ))
        c.status = body.status

    for field in [
        "name", "notes", "email", "phone",
        "years_of_experience", "salary_expectation", "location", "availability",
        "recruiter_notes", "interview_notes", "client_feedback",
        "rejection_reason", "tags",
        "candidate_rate", "candidate_rate_currency", "candidate_rate_period",
    ]:
        val = getattr(body, field)
        if val is not None:
            setattr(c, field, val)

    db.commit()
    db.refresh(c)
    analysis = db.get(AnalysisResult, c.ai_analysis_id) if c.ai_analysis_id else None
    return _candidate_to_response(c, analysis, db=db)


@router.delete("/api/candidates/{candidate_id}", status_code=204)
def delete_candidate(candidate_id: int, db: Session = Depends(get_db)):
    c = db.get(Candidate, candidate_id)
    if not c:
        raise HTTPException(status_code=404, detail="Candidate not found")
    db.delete(c)
    db.commit()


@router.post("/api/candidates/{candidate_id}/score", response_model=CandidateResponse)
async def score_candidate(candidate_id: int, db: Session = Depends(get_db)):
    """Run Mode D (candidate score) for a single candidate vs their position's JD."""
    c = db.get(Candidate, candidate_id)
    if not c:
        raise HTTPException(status_code=404, detail="Candidate not found")

    pos = db.get(Position, c.position_id)
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")
    if not pos.jd_document_id:
        raise HTTPException(status_code=422, detail="Position has no JD document — cannot score")
    if not c.resume_document_id:
        raise HTTPException(status_code=422, detail="Candidate has no resume document — cannot score")

    jd_doc = db.get(Document, pos.jd_document_id)
    resume_doc = db.get(Document, c.resume_document_id)
    if not jd_doc or jd_doc.status != "processed":
        raise HTTPException(status_code=422, detail="JD document is not yet processed")
    if not resume_doc or resume_doc.status != "processed":
        raise HTTPException(status_code=422, detail="Resume document is not yet processed")

    from app.services.analysis import get_analysis_engine
    engine = get_analysis_engine()
    result = await engine.candidate_score(
        c.resume_document_id,
        pos.jd_document_id,
        interview_notes=c.interview_notes,
        client_feedback=c.client_feedback,
    )

    raw_score = result.get("overall_score")
    score = raw_score if raw_score is not None else result.get("score")
    raw_verdict = result.get("verdict")
    verdict = raw_verdict if raw_verdict is not None else result.get("recommendation")

    if isinstance(score, (int, float)):
        c.ai_score = float(score)
    if isinstance(verdict, str):
        c.ai_verdict = verdict
    c.ai_analysis_id = result.get("result_id")

    db.add(CandidateEvent(
        candidate_id=c.id,
        event_type="scored",
        event_data={"score": c.ai_score, "verdict": c.ai_verdict},
    ))
    db.commit()
    db.refresh(c)
    analysis_orm = db.get(AnalysisResult, c.ai_analysis_id) if c.ai_analysis_id else None
    return _candidate_to_response(c, analysis_orm, include_resume=True, db=db)


@router.post("/api/positions/{position_id}/score-all", response_model=list[CandidateResponse])
async def score_all_candidates(position_id: int, db: Session = Depends(get_db)):
    """Run Mode D on all unscored candidates using a single batch LLM call (up to 8 per call)."""
    pos = db.get(Position, position_id)
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")
    if not pos.jd_document_id:
        all_c = db.query(Candidate).filter(Candidate.position_id == position_id).all()
        return [_candidate_to_response(c, db=db) for c in all_c]

    unscored = (
        db.query(Candidate)
        .filter(Candidate.position_id == position_id, Candidate.ai_score.is_(None))
        .all()
    )

    # Separate candidates that can be scored (processed resume) from those that can't
    candidates_data: list[dict] = []
    skipped: list[Candidate] = []

    for c in unscored:
        if not c.resume_document_id:
            skipped.append(c)
            continue
        resume_doc = db.get(Document, c.resume_document_id)
        if not resume_doc or resume_doc.status != "processed":
            skipped.append(c)
            continue
        ed = (
            db.query(ExtractedData)
            .filter_by(document_id=c.resume_document_id)
            .order_by(ExtractedData.id.desc())
            .first()
        )
        if not ed:
            skipped.append(c)
            continue
        candidates_data.append({
            "id": c.id,
            "resume_data": ed.structured_data or {},
            "resume_document_id": c.resume_document_id,
            "interview_notes": c.interview_notes,
            "client_feedback": c.client_feedback,
        })

    results: list[CandidateResponse] = []

    if candidates_data:
        from app.services.analysis import get_analysis_engine
        engine = get_analysis_engine()
        try:
            batch_results = await engine.batch_candidate_score(candidates_data, pos.jd_document_id)
        except Exception:
            logger.exception("Batch scoring failed for position %d", position_id)
            batch_results = {}

        for c_info in candidates_data:
            c = db.get(Candidate, c_info["id"])
            result = batch_results.get(c.id)
            if result:
                raw_score = result.get("overall_score")
                score = raw_score if raw_score is not None else result.get("score")
                raw_verdict = result.get("verdict")
                verdict = raw_verdict if raw_verdict is not None else result.get("recommendation")
                if isinstance(score, (int, float)):
                    c.ai_score = float(score)
                if isinstance(verdict, str):
                    c.ai_verdict = verdict
                c.ai_analysis_id = result.get("result_id")
                db.add(CandidateEvent(
                    candidate_id=c.id,
                    event_type="scored",
                    event_data={"score": c.ai_score, "verdict": c.ai_verdict},
                ))
                db.commit()
                db.refresh(c)
            analysis_orm = db.get(AnalysisResult, c.ai_analysis_id) if c.ai_analysis_id else None
            results.append(_candidate_to_response(c, analysis_orm, db=db))

    for c in skipped:
        results.append(_candidate_to_response(c, db=db))

    return results


# ── Project-level: all candidates ─────────────────────────────────────────────

@router.get("/api/projects/{project_id}/candidates", response_model=CandidateList)
def list_project_candidates(project_id: int, db: Session = Depends(get_db)):
    """All candidates across all positions in a project."""
    from app.models.database import Position as Pos

    candidates = (
        db.query(Candidate)
        .join(Pos, Candidate.position_id == Pos.id)
        .filter(Pos.project_id == project_id)
        .order_by(Candidate.ai_score.desc().nullslast(), Candidate.created_at.asc())
        .all()
    )
    items = []
    for c in candidates:
        analysis = db.get(AnalysisResult, c.ai_analysis_id) if c.ai_analysis_id else None
        items.append(_candidate_to_response(c, analysis, db=db))
    return CandidateList(items=items, total=len(items))
