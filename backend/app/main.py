import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import settings
from app.models.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure all required directories exist
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.CHROMA_DIR, exist_ok=True)
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    if db_path and not db_path.startswith("/"):
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    # Create DB tables
    Base.metadata.create_all(bind=engine)

    # Start background job queue worker
    from app.services import job_queue
    await job_queue.start_worker()

    yield

    # Shutdown
    job_queue.stop_worker()


app = FastAPI(title="TalentLens API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
from app.api import analysis, documents, jobs, projects, search  # noqa: E402

app.include_router(projects.router)
app.include_router(documents.router)
app.include_router(jobs.router)
app.include_router(search.router)
app.include_router(analysis.router)


# ── Base routes ───────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"name": "TalentLens API", "version": "0.1.0", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
