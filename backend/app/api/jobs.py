"""
Job status and SSE streaming — /api/jobs/{id}
"""
import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session

from app.models.database import ProcessingJob, get_db
from app.schemas.schemas import ProcessingJobResponse

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=ProcessingJobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(ProcessingJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/stream")
async def stream_job(job_id: int, db: Session = Depends(get_db)):
    """SSE endpoint — streams job progress events until completion."""
    from app.services import job_queue

    job = db.get(ProcessingJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # If already finished, return immediately without subscribing
    if job.status in ("completed", "failed"):
        async def immediate() -> AsyncGenerator:
            yield {"data": json.dumps({"status": job.status, "progress": job.progress})}

        return EventSourceResponse(immediate())

    # Subscribe to the SSE channel for this job
    channel = job_queue.get_or_create_channel(job_id)

    async def event_generator() -> AsyncGenerator:
        try:
            while True:
                try:
                    event = await asyncio.wait_for(channel.get(), timeout=30.0)
                    yield {"data": json.dumps(event)}
                    if event.get("status") in ("completed", "failed"):
                        break
                except asyncio.TimeoutError:
                    # Heartbeat to keep the connection alive
                    yield {"event": "ping", "data": ""}
        finally:
            job_queue.remove_channel(job_id)

    return EventSourceResponse(event_generator())
