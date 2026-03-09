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
    analysis_mode = Column(String(1), nullable=False)  # A/B/C/D
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
