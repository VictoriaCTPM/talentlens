"""
Projects CRUD — /api/projects
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.database import Document, Project, get_db
from app.schemas.schemas import ProjectCreate, ProjectList, ProjectResponse

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(**body.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=ProjectList)
def list_projects(db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    return ProjectList(items=projects, total=len(projects))


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: int, body: ProjectCreate, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    for field, value in body.model_dump().items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


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
        except Exception:
            pass

    db.delete(project)
    db.commit()
