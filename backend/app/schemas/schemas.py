from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------

class ProjectCreate(BaseModel):
    name: str
    client_name: str
    description: Optional[str] = None
    status: str = "active"


class ProjectResponse(BaseModel):
    id: int
    name: str
    client_name: str
    description: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectList(BaseModel):
    items: list[ProjectResponse]
    total: int


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------

class DocumentUploadResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_type: str
    file_size: int
    status: str
    project_id: int
    created_at: datetime
    job_id: Optional[int] = None

    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    id: int
    project_id: int
    filename: str
    original_filename: str
    file_type: str
    doc_type: Optional[str]
    file_size: int
    status: str
    error_message: Optional[str]
    content_hash: Optional[str]
    created_at: datetime
    processed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class DocumentList(BaseModel):
    items: list[DocumentResponse]
    total: int


class ExtractedDataResponse(BaseModel):
    id: int
    doc_type: str
    structured_data: dict[str, Any]
    extraction_model: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentDetailResponse(DocumentResponse):
    """DocumentResponse extended with extracted structured data."""
    extracted_data: list[ExtractedDataResponse] = []


# ---------------------------------------------------------------------------
# Processing Job
# ---------------------------------------------------------------------------

class ProcessingJobResponse(BaseModel):
    id: int
    document_id: int
    job_type: str
    status: str
    progress: int
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Extracted document profiles
# ---------------------------------------------------------------------------

class ResumeProfile(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    years_of_experience: Optional[float] = None
    current_title: Optional[str] = None
    skills: list[str] = []
    languages: list[str] = []
    education: list[dict[str, Any]] = []
    work_history: list[dict[str, Any]] = []
    summary: Optional[str] = None


class JobDescriptionProfile(BaseModel):
    title: Optional[str] = None
    client_name: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    seniority_level: Optional[str] = None
    required_skills: list[str] = []
    preferred_skills: list[str] = []
    responsibilities: list[str] = []
    requirements: list[str] = []
    salary_range: Optional[str] = None


class WeeklyReportProfile(BaseModel):
    report_date: Optional[str] = None
    project_name: Optional[str] = None
    author: Optional[str] = None
    candidates_submitted: list[dict[str, Any]] = []
    candidates_interviewed: list[dict[str, Any]] = []
    candidates_placed: list[dict[str, Any]] = []
    blockers: list[str] = []
    next_steps: list[str] = []
    notes: Optional[str] = None


class InterviewResultProfile(BaseModel):
    candidate_name: Optional[str] = None
    interviewer: Optional[str] = None
    interview_date: Optional[str] = None
    position: Optional[str] = None
    overall_rating: Optional[str] = None  # strong_yes/yes/no/strong_no
    technical_score: Optional[float] = None
    cultural_score: Optional[float] = None
    strengths: list[str] = []
    weaknesses: list[str] = []
    recommendation: Optional[str] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Analysis Result
# ---------------------------------------------------------------------------

class AnalysisResultResponse(BaseModel):
    id: int
    project_id: int
    analysis_mode: str          # A/B/C/D
    input_document_ids: list[int]
    result_data: dict[str, Any]
    confidence_score: Optional[float]
    source_citations: Optional[list[Any]]   # strings or dicts from LLM
    model_used: str
    prompt_version: str
    created_at: datetime

    model_config = {"from_attributes": True}
