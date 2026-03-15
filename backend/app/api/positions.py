"""
Positions API — /api/projects/{project_id}/positions and /api/positions
Also includes GET /api/pipeline for the pipeline monitor.
"""
import hashlib
import os
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.database import (
    Candidate, Document, ExtractedData, Position, ProcessingJob, Project, get_db,
)
from app.schemas.schemas import (
    PipelinePositionResponse,
    PositionList,
    PositionResponse,
    PositionUpdate,
)

router = APIRouter(tags=["positions"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _jd_enrichment(pos: Position, db: Session) -> dict[str, Any]:
    """Return jd_processing_status, jd_job_id, jd_summary for a position."""
    if not pos.jd_document_id:
        return {"jd_processing_status": None, "jd_job_id": None, "jd_summary": None}

    doc = db.get(Document, pos.jd_document_id)
    if not doc:
        return {"jd_processing_status": None, "jd_job_id": None, "jd_summary": None}

    # Latest processing job for this document
    job = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.document_id == doc.id)
        .order_by(ProcessingJob.created_at.desc())
        .first()
    )

    jd_summary: Optional[dict] = None
    if doc.extracted_data:
        jd_summary = doc.extracted_data[0].structured_data

    return {
        "jd_processing_status": doc.status,
        "jd_job_id": job.id if job else None,
        "jd_summary": jd_summary,
    }


def _position_to_response(pos: Position, db: Session) -> PositionResponse:
    count = (
        db.query(func.count(Candidate.id))
        .filter(Candidate.position_id == pos.id)
        .scalar() or 0
    )
    jd = _jd_enrichment(pos, db)
    return PositionResponse(
        id=pos.id,
        project_id=pos.project_id,
        title=pos.title,
        level=pos.level,
        status=pos.status,
        jd_document_id=pos.jd_document_id,
        days_open=pos.days_open,
        candidates_count=count,
        created_at=pos.created_at,
        closed_at=pos.closed_at,
        jd_processing_status=jd["jd_processing_status"],
        jd_job_id=jd["jd_job_id"],
        jd_summary=jd["jd_summary"],
        client_rate=pos.client_rate,
        client_rate_currency=pos.client_rate_currency,
        client_rate_period=pos.client_rate_period,
    )


def _status_label(days_open: int) -> str:
    if days_open > 30:
        return "Critical"
    if days_open > 20:
        return "Slow"
    return "On Track"


async def _save_jd_file(
    file: UploadFile,
    project_id: int,
    db: Session,
) -> tuple[Document, ProcessingJob]:
    """Save uploaded JD file, create Document + ProcessingJob, enqueue."""
    from app.config.settings import settings
    from app.services import job_queue

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in {".pdf", ".doc", ".docx", ".txt"}:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    content = await file.read()
    content_hash = hashlib.sha256(content).hexdigest()

    # Dedup — reuse existing document if same content
    existing = db.query(Document).filter(Document.content_hash == content_hash).first()
    if existing:
        job = (
            db.query(ProcessingJob)
            .filter(ProcessingJob.document_id == existing.id)
            .order_by(ProcessingJob.created_at.desc())
            .first()
        )
        return existing, job

    safe_name = f"{uuid.uuid4().hex}{ext}"
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(settings.UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as f:
        f.write(content)

    doc = Document(
        project_id=project_id,
        filename=safe_name,
        original_filename=file.filename or safe_name,
        file_path=file_path,
        file_type=ext.lstrip("."),
        doc_type="jd",
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
    return doc, job


# ── Project-scoped create endpoint ────────────────────────────────────────────

@router.post("/api/projects/{project_id}/positions", response_model=PositionResponse, status_code=201)
async def create_position(
    project_id: int,
    title: str = Form(default=""),
    level: str = Form(default=""),
    jd_document_id: int = Form(default=0),
    file: UploadFile = File(default=None),
    db: Session = Depends(get_db),
):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    resolved_doc_id: Optional[int] = jd_document_id if jd_document_id else None
    resolved_title = title.strip() or None
    resolved_job_id: Optional[int] = None

    # Mode B: new file upload
    if file and file.filename:
        doc, job = await _save_jd_file(file, project_id, db)
        resolved_doc_id = doc.id
        resolved_job_id = job.id if job else None
        # Try to extract title from already-processed doc
        if not resolved_title and doc.extracted_data:
            resolved_title = doc.extracted_data[0].structured_data.get("title")
        if not resolved_title:
            resolved_title = os.path.splitext(doc.original_filename)[0]

    # Mode A: reference existing doc — try to auto-fill title
    elif resolved_doc_id and not resolved_title:
        doc = db.get(Document, resolved_doc_id)
        if doc and doc.extracted_data:
            resolved_title = doc.extracted_data[0].structured_data.get("title")
        if doc and not resolved_title:
            resolved_title = os.path.splitext(doc.original_filename)[0]

    pos = Position(
        project_id=project_id,
        title=resolved_title or "Open Position",
        level=level.strip() or None,
        jd_document_id=resolved_doc_id,
        status="open",
    )
    db.add(pos)
    db.commit()
    db.refresh(pos)
    return _position_to_response(pos, db)


# ── Project-scoped list ────────────────────────────────────────────────────────

@router.get("/api/projects/{project_id}/positions", response_model=PositionList)
def list_positions(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    positions = (
        db.query(Position)
        .filter(Position.project_id == project_id)
        .order_by(Position.created_at.desc())
        .all()
    )
    items = [_position_to_response(p, db) for p in positions]
    return PositionList(items=items, total=len(items))


# ── Single position endpoints ─────────────────────────────────────────────────

@router.get("/api/positions/{position_id}", response_model=PositionResponse)
def get_position(position_id: int, db: Session = Depends(get_db)):
    pos = db.get(Position, position_id)
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")
    return _position_to_response(pos, db)


@router.put("/api/positions/{position_id}", response_model=PositionResponse)
def update_position(position_id: int, body: PositionUpdate, db: Session = Depends(get_db)):
    pos = db.get(Position, position_id)
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")

    if body.title is not None:
        pos.title = body.title
    if body.level is not None:
        pos.level = body.level
    if body.status is not None:
        old_status = pos.status
        pos.status = body.status
        if body.status in ("closed", "filled") and old_status == "open":
            pos.closed_at = datetime.utcnow()
    if body.client_rate is not None:
        pos.client_rate = body.client_rate
    if body.client_rate_currency is not None:
        pos.client_rate_currency = body.client_rate_currency
    if body.client_rate_period is not None:
        pos.client_rate_period = body.client_rate_period

    db.commit()
    db.refresh(pos)
    return _position_to_response(pos, db)


@router.put("/api/positions/{position_id}/jd", response_model=PositionResponse)
async def replace_jd(
    position_id: int,
    jd_document_id: int = Form(default=0),
    file: UploadFile = File(default=None),
    db: Session = Depends(get_db),
):
    """Replace or add a JD to an existing position (upload new file OR link existing doc)."""
    pos = db.get(Position, position_id)
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")

    if file and file.filename:
        doc, _job = await _save_jd_file(file, pos.project_id, db)
        pos.jd_document_id = doc.id
        # Auto-update title if position had a generic one and JD is already processed
        if pos.title in ("Open Position", "") and doc.extracted_data:
            pos.title = doc.extracted_data[0].structured_data.get("title") or pos.title
    elif jd_document_id:
        doc = db.get(Document, jd_document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        pos.jd_document_id = jd_document_id

    db.commit()
    db.refresh(pos)
    return _position_to_response(pos, db)


@router.delete("/api/positions/{position_id}", status_code=204)
def delete_position(position_id: int, db: Session = Depends(get_db)):
    pos = db.get(Position, position_id)
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")
    db.delete(pos)
    db.commit()


# ── Pipeline Monitor ──────────────────────────────────────────────────────────

@router.get("/api/pipeline", response_model=list[PipelinePositionResponse])
def get_pipeline(db: Session = Depends(get_db)):
    """All open positions across all projects, sorted by days_open DESC."""
    positions = (
        db.query(Position)
        .filter(Position.status == "open")
        .order_by(Position.created_at.asc())
        .all()
    )

    results = []
    for pos in positions:
        project = db.get(Project, pos.project_id)
        count = (
            db.query(func.count(Candidate.id))
            .filter(Candidate.position_id == pos.id)
            .scalar() or 0
        )
        days = pos.days_open
        results.append(PipelinePositionResponse(
            id=pos.id,
            title=pos.title,
            project_id=pos.project_id,
            project_name=project.name if project else "—",
            client_name=project.client_name if project else "—",
            days_open=days,
            candidates_count=count,
            status=pos.status,
            status_label=_status_label(days),
        ))

    results.sort(key=lambda r: r.days_open, reverse=True)
    return results
