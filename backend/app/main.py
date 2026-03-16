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

    # Warm up embeddings model (triggers download/load before first request)
    from app.services.embeddings import get_embedding_service
    get_embedding_service()

    # Start background job queue worker
    from app.services import job_queue
    await job_queue.start_worker()

    yield

    # Shutdown
    job_queue.stop_worker()


app = FastAPI(title="TalentLens API", version="0.1.0", lifespan=lifespan)

_cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
from app.api import analysis, candidates, documents, jobs, positions, projects, search, team  # noqa: E402

app.include_router(projects.router)
app.include_router(documents.router)
app.include_router(jobs.router)
app.include_router(search.router)
app.include_router(analysis.router)
app.include_router(positions.router)
app.include_router(candidates.router)
app.include_router(team.router)


# ── Base routes ───────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"name": "TalentLens API", "version": "0.1.0", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/api/health")
async def api_health():
    return {"status": "ok", "service": "talentlens-backend"}
