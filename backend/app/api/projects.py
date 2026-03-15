"""
Projects CRUD — /api/projects
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.models.database import Candidate, Document, Position, Project, TeamMember, get_db
from app.schemas.schemas import ProjectCreate, ProjectList, ProjectResponse

router = APIRouter(prefix="/api/projects", tags=["projects"])


# ── Helper ─────────────────────────────────────────────────────────────────────

def _enrich(project: Project, db: Session) -> ProjectResponse:
    """Build ProjectResponse with live position/candidate stats."""
    positions = db.query(Position).filter(Position.project_id == project.id).all()
    open_positions = [p for p in positions if p.status == "open"]

    total_candidates = (
        db.query(func.count(Candidate.id))
        .join(Position, Candidate.position_id == Position.id)
        .filter(Position.project_id == project.id)
        .scalar() or 0
    )

    team_members_count = (
        db.query(func.count(TeamMember.id))
        .filter(TeamMember.project_id == project.id, TeamMember.status == "active")
        .scalar() or 0
    )

    open_days = [p.days_open for p in open_positions]
    avg_days_open = (sum(open_days) / len(open_days)) if open_days else None

    if any(d > 30 for d in open_days):
        health_status = "at_risk"
    elif any(d > 20 for d in open_days):
        health_status = "attention"
    else:
        health_status = "healthy"

    return ProjectResponse(
        id=project.id,
        name=project.name,
        client_name=project.client_name,
        description=project.description,
        status=project.status,
        created_at=project.created_at,
        updated_at=project.updated_at,
        open_positions_count=len(open_positions),
        total_candidates_count=total_candidates,
        avg_days_open=avg_days_open,
        health_status=health_status,
        team_members_count=team_members_count,
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(**body.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return _enrich(project, db)


@router.get("", response_model=ProjectList)
def list_projects(db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    return ProjectList(items=[_enrich(p, db) for p in projects], total=len(projects))


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _enrich(project, db)


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: int, body: ProjectCreate, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    for field, value in body.model_dump().items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return _enrich(project, db)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Delete ChromaDB chunks for every document in this project
    from app.services.vector_store import get_vector_store
    vs = get_vector_store()
    for doc in project.documents:
        try:
            vs.delete_by_document(doc.id)
        except Exception as e:
            logger.warning("Failed to delete ChromaDB chunks for document %s: %s", doc.id, e)

    db.delete(project)
    db.commit()
