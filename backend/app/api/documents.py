"""
Document upload and management — /api/projects/{project_id}/documents, /api/documents/{id}
"""
import hashlib
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.models.database import Document, ProcessingJob, Project, get_db
from app.schemas.schemas import (
    DocumentDetailResponse,
    DocumentList,
    DocumentUploadResponse,
)

router = APIRouter(tags=["documents"])

ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "txt"}


def _ext(filename: str) -> str:
    return Path(filename).suffix.lstrip(".").lower()


# ── Upload ────────────────────────────────────────────────────────────────────

@router.post(
    "/api/projects/{project_id}/documents",
    response_model=DocumentUploadResponse,
    status_code=201,
)
async def upload_document(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    from app.services import job_queue

    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    ext = _ext(file.filename or "")
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    file_size = len(content)

    # SHA-256 duplicate detection within the same project
    content_hash = hashlib.sha256(content).hexdigest()
    duplicate = (
        db.query(Document)
        .filter_by(content_hash=content_hash, project_id=project_id)
        .first()
    )
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail=f"Duplicate: this file was already uploaded as document_id={duplicate.id}",
        )

    # Save file to UPLOAD_DIR/{project_id}/{uuid}.{ext}
    upload_dir = Path(settings.UPLOAD_DIR) / str(project_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    file_path = upload_dir / unique_name
    file_path.write_bytes(content)

    # Create Document record
    doc = Document(
        project_id=project_id,
        filename=unique_name,
        original_filename=file.filename,
        file_path=str(file_path),
        file_type=ext,
        file_size=file_size,
        content_hash=content_hash,
        status="queued",
    )
    db.add(doc)
    db.flush()  # populate doc.id before creating the job

    # Create ProcessingJob
    job = ProcessingJob(
        document_id=doc.id,
        job_type="process_document",
        status="queued",
        progress=0,
    )
    db.add(job)
    db.commit()
    db.refresh(doc)
    db.refresh(job)

    # Enqueue for background processing
    await job_queue.enqueue(doc.id, job.id)

    # Return document + job_id for frontend to track processing status
    return {
        "id": doc.id,
        "filename": doc.filename,
        "original_filename": doc.original_filename,
        "file_type": doc.file_type,
        "file_size": doc.file_size,
        "status": doc.status,
        "project_id": doc.project_id,
        "created_at": doc.created_at,
        "job_id": job.id,
    }


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("/api/projects/{project_id}/documents", response_model=DocumentList)
def list_documents(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    docs = (
        db.query(Document)
        .filter_by(project_id=project_id)
        .order_by(Document.created_at.desc())
        .all()
    )
    return DocumentList(items=docs, total=len(docs))


# ── Detail ────────────────────────────────────────────────────────────────────

@router.get("/api/documents/{document_id}", response_model=DocumentDetailResponse)
def get_document(document_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/api/documents/{document_id}", status_code=204)
def delete_document(document_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Remove chunks from ChromaDB
    from app.services.vector_store import get_vector_store
    try:
        get_vector_store().delete_by_document(doc.id)
    except Exception:
        pass

    # Remove file from disk
    try:
        if os.path.exists(doc.file_path):
            os.remove(doc.file_path)
    except Exception:
        pass

    db.delete(doc)
    db.commit()
