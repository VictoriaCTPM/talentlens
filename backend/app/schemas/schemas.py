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
    # enriched stats (populated by API, not ORM)
    open_positions_count: int = 0
    total_candidates_count: int = 0
    avg_days_open: Optional[float] = None
    health_status: str = "healthy"   # healthy / attention / at_risk
    team_members_count: int = 0

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
    team_member_id: Optional[int] = None
    developer_name_hint: Optional[str] = None

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


# ---------------------------------------------------------------------------
# Position
# ---------------------------------------------------------------------------

class PositionCreate(BaseModel):
    title: str
    project_id: int
    jd_document_id: Optional[int] = None
    level: Optional[str] = None   # junior/mid/senior/lead


class PositionUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None   # open/paused/closed/filled
    level: Optional[str] = None
    client_rate: Optional[float] = None
    client_rate_currency: Optional[str] = None
    client_rate_period: Optional[str] = None


class PositionResponse(BaseModel):
    id: int
    project_id: int
    title: str
    level: Optional[str]
    status: str
    jd_document_id: Optional[int]
    days_open: int
    candidates_count: int = 0
    created_at: datetime
    closed_at: Optional[datetime]
    # JD enrichment (populated by API, not ORM)
    jd_processing_status: Optional[str] = None   # uploaded/queued/processing/processed/error
    jd_job_id: Optional[int] = None              # for SSE polling
    jd_summary: Optional[dict[str, Any]] = None  # extracted JD structured data
    # Rate fields
    client_rate: Optional[float] = None
    client_rate_currency: Optional[str] = None
    client_rate_period: Optional[str] = None

    model_config = {"from_attributes": True}


class PositionList(BaseModel):
    items: list[PositionResponse]
    total: int


# ---------------------------------------------------------------------------
# Candidate
# ---------------------------------------------------------------------------

class CandidateCreate(BaseModel):
    name: str
    email: Optional[str] = None
    resume_document_id: Optional[int] = None
    notes: Optional[str] = None


class CandidateUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    years_of_experience: Optional[float] = None
    salary_expectation: Optional[str] = None
    location: Optional[str] = None
    availability: Optional[str] = None
    recruiter_notes: Optional[str] = None
    interview_notes: Optional[str] = None
    client_feedback: Optional[str] = None
    rejection_reason: Optional[str] = None
    tags: Optional[list[str]] = None
    candidate_rate: Optional[float] = None
    candidate_rate_currency: Optional[str] = None
    candidate_rate_period: Optional[str] = None


class CandidateResponse(BaseModel):
    id: int
    position_id: int
    name: str
    email: Optional[str]
    resume_document_id: Optional[int]
    status: str
    ai_score: Optional[float]
    ai_verdict: Optional[str]
    ai_analysis_id: Optional[int]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    # Profile fields
    phone: Optional[str] = None
    years_of_experience: Optional[float] = None
    salary_expectation: Optional[str] = None
    location: Optional[str] = None
    availability: Optional[str] = None
    recruiter_notes: Optional[str] = None
    interview_notes: Optional[str] = None
    client_feedback: Optional[str] = None
    rejection_reason: Optional[str] = None
    tags: Optional[list[str]] = None
    # Rate fields
    candidate_rate: Optional[float] = None
    candidate_rate_currency: Optional[str] = None
    candidate_rate_period: Optional[str] = None
    # Computed enrichment (not from ORM, populated at query time)
    skill_match_score: Optional[float] = None
    scored_at: Optional[datetime] = None
    resume_extracted: Optional[dict[str, Any]] = None
    margin: Optional[dict[str, Any]] = None

    model_config = {"from_attributes": True}


class CandidateList(BaseModel):
    items: list[CandidateResponse]
    total: int


class CandidateEventResponse(BaseModel):
    id: int
    candidate_id: int
    event_type: str
    event_data: Optional[dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class PipelinePositionResponse(BaseModel):
    id: int
    title: str
    project_id: int
    project_name: str
    client_name: str
    days_open: int
    candidates_count: int
    status: str
    status_label: str   # "Critical" / "Slow" / "On Track"


# ---------------------------------------------------------------------------
# Team Member
# ---------------------------------------------------------------------------

class TeamMemberCreate(BaseModel):
    name: str
    role: str
    level: Optional[str] = None
    start_date: Optional[datetime] = None
    notes: Optional[str] = None


class TeamMemberUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    level: Optional[str] = None
    start_date: Optional[datetime] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    skills: Optional[list[str]] = None


class TeamMemberResponse(BaseModel):
    id: int
    project_id: int
    name: str
    role: str
    level: Optional[str]
    start_date: Optional[datetime]
    status: str
    resume_document_id: Optional[int]
    skills: Optional[list[str]]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    # Computed fields (populated by API, not ORM)
    resume_summary: Optional[dict[str, Any]] = None
    reports_count: int = 0
    last_report_date: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TeamMemberList(BaseModel):
    items: list[TeamMemberResponse]
    total: int
    overview: Optional[dict[str, Any]] = None  # skills matrix + role summary
