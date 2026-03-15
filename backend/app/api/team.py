"""
Team API — /api/projects/{project_id}/team and /api/team
"""
import hashlib
import os
import uuid
from collections import Counter, defaultdict
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

import logging

from app.models.database import Candidate, Document, ExtractedData, ProcessingJob, ReportMemberLink, TeamMember, get_db
from app.schemas.schemas import TeamMemberList, TeamMemberResponse, TeamMemberUpdate

router = APIRouter(tags=["team"])
logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _reports_for_member(member_id: int, db: Session) -> list[Document]:
    return (
        db.query(Document)
        .filter(Document.team_member_id == member_id, Document.doc_type.in_(["report", "client_report", "interview"]))
        .order_by(Document.created_at.desc())
        .all()
    )


def _resume_summary(resume_document_id: Optional[int], db: Session) -> Optional[dict]:
    if not resume_document_id:
        return None
    ed = (
        db.query(ExtractedData)
        .filter(ExtractedData.document_id == resume_document_id)
        .first()
    )
    return ed.structured_data if ed else None


def _member_to_response(m: TeamMember, db: Session) -> TeamMemberResponse:
    reports = _reports_for_member(m.id, db)
    last_report = reports[0].created_at if reports else None
    summary = _resume_summary(m.resume_document_id, db)
    hired_from = db.query(Candidate).filter_by(team_member_id=m.id).first()
    return TeamMemberResponse(
        id=m.id,
        project_id=m.project_id,
        name=m.name,
        role=m.role,
        level=m.level,
        start_date=m.start_date,
        status=m.status,
        resume_document_id=m.resume_document_id,
        skills=m.skills,
        notes=m.notes,
        created_at=m.created_at,
        updated_at=m.updated_at,
        resume_summary=summary,
        reports_count=len(reports),
        last_report_date=last_report,
        hired_from_candidate_id=hired_from.id if hired_from else None,
        hired_from_position_id=hired_from.position_id if hired_from else None,
    )


def _build_overview(members: list[TeamMember]) -> dict:
    """Build skills matrix and role summary for AI context."""
    # Skills frequency across team
    all_skills: list[str] = []
    for m in members:
        if m.skills:
            all_skills.extend(m.skills)
    skill_counts = Counter(all_skills)
    skills_matrix = [
        {"skill": sk, "count": cnt, "members": [m.name for m in members if m.skills and sk in m.skills]}
        for sk, cnt in skill_counts.most_common(20)
    ]

    # Role grouping
    role_groups: dict[str, list[str]] = defaultdict(list)
    for m in members:
        role_groups[m.role].append(m.name)
    roles = [{"role": role, "count": len(names), "members": names} for role, names in role_groups.items()]

    return {
        "total_members": len(members),
        "active_count": sum(1 for m in members if m.status == "active"),
        "roles": roles,
        "skills_matrix": skills_matrix,
        "top_skills": [s["skill"] for s in skills_matrix[:10]],
    }


def _sync_skills_from_resume(member: TeamMember, db: Session) -> None:
    """Pull skills list from the member's processed resume ExtractedData."""
    if not member.resume_document_id:
        return
    ed = (
        db.query(ExtractedData)
        .filter(ExtractedData.document_id == member.resume_document_id)
        .first()
    )
    if not ed:
        return
    data = ed.structured_data or {}
    skills = data.get("skills") or data.get("required_skills") or []
    if skills and isinstance(skills, list):
        member.skills = [str(s) for s in skills[:30]]
        db.commit()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/api/projects/{project_id}/team", response_model=TeamMemberList)
def list_team(project_id: int, db: Session = Depends(get_db)):
    members = (
        db.query(TeamMember)
        .filter(TeamMember.project_id == project_id)
        .order_by(TeamMember.role, TeamMember.name)
        .all()
    )
    overview = _build_overview(members)
    return TeamMemberList(
        items=[_member_to_response(m, db) for m in members],
        total=len(members),
        overview=overview,
    )


@router.post("/api/projects/{project_id}/team", response_model=TeamMemberResponse, status_code=201)
async def add_team_member(
    project_id: int,
    name: str = Form(...),
    role: str = Form(...),
    level: str = Form(default=""),
    start_date: str = Form(default=""),
    notes: str = Form(default=""),
    file: UploadFile = File(default=None),
    db: Session = Depends(get_db),
):
    from app.config.settings import settings
    from app.services import job_queue

    parsed_start: Optional[datetime] = None
    if start_date.strip():
        try:
            parsed_start = datetime.fromisoformat(start_date.strip())
        except ValueError:
            pass

    member = TeamMember(
        project_id=project_id,
        name=name.strip(),
        role=role.strip(),
        level=level.strip() or None,
        start_date=parsed_start,
        notes=notes.strip() or None,
        status="active",
    )
    db.add(member)
    db.flush()

    if file and file.filename:
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in {".pdf", ".doc", ".docx", ".txt"}:
            raise HTTPException(status_code=400, detail="Unsupported file type")

        content = await file.read()
        content_hash = hashlib.sha256(content).hexdigest()

        existing = db.query(Document).filter(Document.content_hash == content_hash).first()
        if existing:
            member.resume_document_id = existing.id
        else:
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
                doc_type="resume",
                file_size=len(content),
                status="queued",
                content_hash=content_hash,
                team_member_id=member.id,
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
            member.resume_document_id = doc.id
            await job_queue.enqueue(doc.id, job.id)

    db.commit()
    db.refresh(member)
    _sync_skills_from_resume(member, db)
    return _member_to_response(member, db)


@router.get("/api/team/{member_id}", response_model=TeamMemberResponse)
def get_team_member(member_id: int, db: Session = Depends(get_db)):
    m = db.get(TeamMember, member_id)
    if not m:
        raise HTTPException(status_code=404, detail="Team member not found")
    return _member_to_response(m, db)


@router.put("/api/team/{member_id}", response_model=TeamMemberResponse)
def update_team_member(member_id: int, body: TeamMemberUpdate, db: Session = Depends(get_db)):
    m = db.get(TeamMember, member_id)
    if not m:
        raise HTTPException(status_code=404, detail="Team member not found")
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(m, field, val)
    db.commit()
    db.refresh(m)
    return _member_to_response(m, db)


@router.delete("/api/team/{member_id}", status_code=204)
def delete_team_member(member_id: int, db: Session = Depends(get_db)):
    """Soft delete — sets status to offboarded, preserves data for AI history."""
    m = db.get(TeamMember, member_id)
    if not m:
        raise HTTPException(status_code=404, detail="Team member not found")
    m.status = "offboarded"
    db.commit()


@router.post("/api/team/{member_id}/resume", response_model=TeamMemberResponse)
async def upload_resume(
    member_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload or replace a resume for an existing team member."""
    from app.config.settings import settings
    from app.services import job_queue

    m = db.get(TeamMember, member_id)
    if not m:
        raise HTTPException(status_code=404, detail="Team member not found")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in {".pdf", ".doc", ".docx", ".txt"}:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    content = await file.read()
    content_hash = hashlib.sha256(content).hexdigest()

    existing = db.query(Document).filter(Document.content_hash == content_hash).first()
    if existing:
        m.resume_document_id = existing.id
    else:
        safe_name = f"{uuid.uuid4().hex}{ext}"
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        file_path = os.path.join(settings.UPLOAD_DIR, safe_name)
        with open(file_path, "wb") as f:
            f.write(content)

        doc = Document(
            project_id=m.project_id,
            filename=safe_name,
            original_filename=file.filename or safe_name,
            file_path=file_path,
            file_type=ext.lstrip("."),
            doc_type="resume",
            file_size=len(content),
            status="queued",
            content_hash=content_hash,
            team_member_id=m.id,
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
        m.resume_document_id = doc.id
        await job_queue.enqueue(doc.id, job.id)

    db.commit()
    db.refresh(m)
    _sync_skills_from_resume(m, db)
    return _member_to_response(m, db)


@router.get("/api/team/{member_id}/reports")
def get_member_reports(member_id: int, db: Session = Depends(get_db)):
    """Return all reports/interviews linked to this team member with extracted data."""
    m = db.get(TeamMember, member_id)
    if not m:
        raise HTTPException(status_code=404, detail="Team member not found")
    reports = _reports_for_member(member_id, db)
    items = []
    for doc in reports:
        extracted = doc.extracted_data[0].structured_data if doc.extracted_data else None
        items.append({
            "id": doc.id,
            "original_filename": doc.original_filename,
            "doc_type": doc.doc_type,
            "file_size": doc.file_size,
            "status": doc.status,
            "created_at": doc.created_at.isoformat(),
            "extracted": extracted,
        })
    return {"items": items, "total": len(items)}


@router.post("/api/team/{member_id}/link-report/{document_id}", response_model=TeamMemberResponse)
def link_report(member_id: int, document_id: int, db: Session = Depends(get_db)):
    """Link an existing report/interview document to this team member."""
    m = db.get(TeamMember, member_id)
    if not m:
        raise HTTPException(status_code=404, detail="Team member not found")
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.team_member_id = member_id
    db.commit()
    return _member_to_response(m, db)


@router.post("/api/team/{member_id}/sync-skills", response_model=TeamMemberResponse)
def sync_skills(member_id: int, db: Session = Depends(get_db)):
    """Re-sync skills from the team member's processed resume."""
    m = db.get(TeamMember, member_id)
    if not m:
        raise HTTPException(status_code=404, detail="Team member not found")
    _sync_skills_from_resume(m, db)
    return _member_to_response(m, db)


# ── Utility (called from job_queue after processing) ──────────────────────────

def _fuzzy_match_member(name: str, members: list[TeamMember]) -> TeamMember | None:
    """Return best-matching TeamMember for a given name string, or None."""
    name_lower = name.strip().lower()
    if not name_lower:
        return None
    # Exact match first
    for m in members:
        if m.name.strip().lower() == name_lower:
            return m
    # Token overlap (≥50%)
    name_parts = set(name_lower.split())
    best_member, best_score = None, 0.0
    for m in members:
        tm_parts = set(m.name.strip().lower().split())
        common = name_parts & tm_parts
        score = len(common) / max(len(name_parts), len(tm_parts), 1)
        if score > best_score and score >= 0.5:
            best_score = score
            best_member = m
    return best_member


def try_link_report_to_team_member(doc_id: int, db: Session) -> None:
    """
    After a report is processed, link it to one or more team members.
    - Consolidated reports: creates ReportMemberLink rows for each matched section.
    - Individual reports: falls back to setting Document.team_member_id (backward compat).
    """
    doc = db.get(Document, doc_id)
    if not doc or doc.doc_type not in ("report", "client_report", "interview"):
        return
    if not doc.extracted_data:
        return

    data = doc.extracted_data[0].structured_data or {}
    members = (
        db.query(TeamMember)
        .filter(TeamMember.project_id == doc.project_id, TeamMember.status == "active")
        .all()
    )
    if not members:
        return

    member_sections = data.get("member_sections", [])

    if member_sections:
        # Consolidated path: link each section to its matched team member
        for section in member_sections:
            section_name = section.get("member_name", "")
            matched = _fuzzy_match_member(section_name, members)
            if matched:
                existing = (
                    db.query(ReportMemberLink)
                    .filter_by(document_id=doc_id, team_member_id=matched.id)
                    .first()
                )
                if not existing:
                    db.add(ReportMemberLink(
                        document_id=doc_id,
                        team_member_id=matched.id,
                        member_name_in_report=section_name,
                        section_data=section,
                    ))
                    logger.info(
                        "Linked report %d section '%s' → team member %d (%s)",
                        doc_id, section_name, matched.id, matched.name,
                    )
                # If only one section and it matched, also set the legacy FK for compatibility
                if len(member_sections) == 1:
                    doc.team_member_id = matched.id
            else:
                logger.warning("Report %d: no match for section '%s'", doc_id, section_name)
        db.commit()
    else:
        # Legacy individual report path
        developer_name = data.get("developer_name") or data.get("author") or data.get("candidate_name") or ""
        matched = _fuzzy_match_member(developer_name, members)
        if matched:
            doc.team_member_id = matched.id
            db.commit()
            logger.info("Linked individual report %d → team member %d", doc_id, matched.id)
