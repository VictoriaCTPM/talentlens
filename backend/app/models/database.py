from datetime import datetime
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text, create_engine
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

from app.config.settings import settings


engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    client_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="active")  # active/completed/paused
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")
    analysis_results = relationship("AnalysisResult", back_populates="project", cascade="all, delete-orphan")
    positions = relationship("Position", back_populates="project", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_type = Column(String(10), nullable=False)   # pdf/doc/docx/txt
    doc_type = Column(String(30), nullable=True)     # jd/resume/report/interview/job_request/client_report
    file_size = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="uploaded")  # uploaded/queued/processing/processed/error
    error_message = Column(Text, nullable=True)
    content_hash = Column(String(64), nullable=True, index=True)  # SHA-256 for dedup
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    team_member_id = Column(Integer, ForeignKey("team_members.id"), nullable=True)

    project = relationship("Project", back_populates="documents")
    extracted_data = relationship("ExtractedData", back_populates="document", cascade="all, delete-orphan")
    processing_jobs = relationship("ProcessingJob", back_populates="document", cascade="all, delete-orphan")


class ExtractedData(Base):
    __tablename__ = "extracted_data"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    doc_type = Column(String(30), nullable=False)
    structured_data = Column(JSON, nullable=False)
    extraction_model = Column(String(100), nullable=False)
    extraction_prompt_version = Column(String(20), nullable=False)
    schema_version = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("Document", back_populates="extracted_data")


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    analysis_mode = Column(String(5), nullable=False)  # A/B/C/D/E/PI
    input_document_ids = Column(JSON, nullable=False)   # list of document ids
    result_data = Column(JSON, nullable=False)
    confidence_score = Column(Float, nullable=True)
    source_citations = Column(JSON, nullable=True)
    model_used = Column(String(100), nullable=False)
    prompt_version = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="analysis_results")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    job_type = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default="queued")  # queued/processing/completed/failed
    progress = Column(Integer, nullable=False, default=0)          # 0-100
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    document = relationship("Document", back_populates="processing_jobs")


# NOTE: AICallLog is write-only (no read API). Kept for observability.
# See docs/DeadCodeAudit.md — decision: keep as audit log.
class AICallLog(Base):
    __tablename__ = "ai_call_logs"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    endpoint = Column(String(200), nullable=True)
    prompt_hash = Column(String(64), nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False)
    cost_estimate = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    level = Column(String(20), nullable=True)   # junior/mid/senior/lead
    status = Column(String(20), nullable=False, default="open")  # open/paused/closed/filled
    jd_document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    closed_at = Column(DateTime, nullable=True)
    client_rate = Column(Float, nullable=True)
    client_rate_currency = Column(String(10), nullable=True, default="USD")
    client_rate_period = Column(String(20), nullable=True)  # hourly/monthly/annual

    project = relationship("Project", back_populates="positions")
    jd_document = relationship("Document", foreign_keys=[jd_document_id])
    candidates = relationship("Candidate", back_populates="position", cascade="all, delete-orphan")

    @property
    def days_open(self) -> int:
        if self.status == "open":
            return (datetime.utcnow() - self.created_at).days
        if self.closed_at:
            return (self.closed_at - self.created_at).days
        return 0


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    resume_document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    status = Column(String(30), nullable=False, default="new")
    # new/screening/technical_interview/client_interview/offer/hired/rejected
    ai_score = Column(Float, nullable=True)
    ai_verdict = Column(String(30), nullable=True)  # strong_fit/moderate_fit/risky/not_recommended
    ai_analysis_id = Column(Integer, ForeignKey("analysis_results.id"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    # Profile fields (auto-populated from resume ExtractedData)
    phone = Column(String(50), nullable=True)
    years_of_experience = Column(Float, nullable=True)
    location = Column(String(255), nullable=True)
    availability = Column(String(100), nullable=True)
    recruiter_notes = Column(Text, nullable=True)
    interview_notes = Column(Text, nullable=True)
    client_feedback = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    tags = Column(JSON, nullable=True)
    candidate_rate = Column(Float, nullable=True)
    candidate_rate_currency = Column(String(10), nullable=True, default="USD")
    candidate_rate_period = Column(String(20), nullable=True)  # hourly/monthly/annual

    position = relationship("Position", back_populates="candidates")
    resume_document = relationship("Document", foreign_keys=[resume_document_id])
    ai_analysis = relationship("AnalysisResult", foreign_keys=[ai_analysis_id])
    events = relationship("CandidateEvent", back_populates="candidate", cascade="all, delete-orphan")


class CandidateEvent(Base):
    __tablename__ = "candidate_events"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)  # created/status_change/scored/note_added
    event_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    candidate = relationship("Candidate", back_populates="events")


class TeamMember(Base):
    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    role = Column(String(255), nullable=False)        # e.g. "Senior Backend Developer"
    level = Column(String(20), nullable=True)          # junior/mid/senior/lead
    start_date = Column(DateTime, nullable=True)
    status = Column(String(20), default="active")     # active / offboarded
    resume_document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    skills = Column(JSON, nullable=True)               # ["Python", "AWS", ...]
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    project = relationship("Project", backref="team_members")
    resume_document = relationship("Document", foreign_keys=[resume_document_id])