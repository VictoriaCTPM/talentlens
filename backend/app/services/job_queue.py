"""
Async document processing queue with SSE event broadcasting.
Full pipeline: parse → classify+extract → chunk → embed → store in ChromaDB.
"""
import asyncio
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Per-job SSE channels: job_id → asyncio.Queue of event dicts
_sse_channels: dict[int, asyncio.Queue] = {}

# Main work queue: items are (document_id, job_id)
_queue: "asyncio.Queue[tuple[int, int]]" = asyncio.Queue()
_worker_task: "asyncio.Task | None" = None


# ── Public API ───────────────────────────────────────────────────────────────

def get_or_create_channel(job_id: int) -> asyncio.Queue:
    """Get (or create) the SSE event channel for a job."""
    if job_id not in _sse_channels:
        _sse_channels[job_id] = asyncio.Queue()
    return _sse_channels[job_id]


def remove_channel(job_id: int) -> None:
    _sse_channels.pop(job_id, None)


async def enqueue(document_id: int, job_id: int) -> None:
    """Add a document processing job to the work queue."""
    await _queue.put((document_id, job_id))
    logger.info("Enqueued job %d for document %d", job_id, document_id)


async def start_worker() -> None:
    """Start the background worker task (called on app startup)."""
    global _worker_task
    _worker_task = asyncio.create_task(_worker_loop())
    logger.info("Job queue worker started")


def stop_worker() -> None:
    """Cancel the worker task (called on app shutdown)."""
    global _worker_task
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        _worker_task = None


# ── Internal ─────────────────────────────────────────────────────────────────

async def _emit(job_id: int, event: dict[str, Any]) -> None:
    """Push an event to the SSE channel for a job (no-op if no subscriber)."""
    ch = _sse_channels.get(job_id)
    if ch:
        await ch.put(event)


async def _worker_loop() -> None:
    """Continuously pull jobs from the queue and process them."""
    while True:
        document_id, job_id = await _queue.get()
        try:
            await _process_document(document_id, job_id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Unexpected worker error for job %d: %s", job_id, exc)
        finally:
            _queue.task_done()


async def _process_document(document_id: int, job_id: int) -> None:
    """Full processing pipeline for one document."""
    from app.models.database import Document, ExtractedData, ProcessingJob, SessionLocal
    from app.services.document_parser import parse_document
    from app.services.document_processor import chunk_document, classify_and_extract
    from app.services.embeddings import get_embedding_service
    from app.services.llm.client import get_llm_client
    from app.services.vector_store import get_vector_store

    db = SessionLocal()
    try:
        # ── 1. Mark as processing ────────────────────────────────────────────
        job = db.get(ProcessingJob, job_id)
        doc = db.get(Document, document_id)
        if not job or not doc:
            logger.error("Job %d or document %d not found in DB", job_id, document_id)
            return

        job.status = "processing"
        job.started_at = datetime.utcnow()
        job.progress = 10
        doc.status = "processing"
        db.commit()
        await _emit(job_id, {"status": "processing", "progress": 10, "step": "parsing"})

        # ── 2. Parse file text ───────────────────────────────────────────────
        raw_text = parse_document(doc.file_path, doc.file_type)
        job.progress = 25
        db.commit()
        await _emit(job_id, {"status": "processing", "progress": 25, "step": "classifying"})

        # ── 3. Classify + extract structured data (single LLM call) ─────────
        llm = get_llm_client()
        result = await classify_and_extract(raw_text, doc.original_filename, llm)
        doc_type = result["doc_type"]
        extracted = result["extracted"]
        doc.doc_type = doc_type
        job.progress = 55
        db.commit()
        await _emit(job_id, {
            "status": "processing", "progress": 55,
            "step": "embedding", "doc_type": doc_type,
        })

        # ── 4. Save extracted data to DB ─────────────────────────────────────
        ed = ExtractedData(
            document_id=document_id,
            doc_type=doc_type,
            structured_data=extracted,
            extraction_model=llm.model_name,
            extraction_prompt_version="1.0",
            schema_version="1.0",
        )
        db.add(ed)
        db.commit()

        # ── 5. Chunk document ────────────────────────────────────────────────
        chunks = chunk_document(raw_text, doc_type, extracted)

        # ── 6. Embed chunks locally (sentence-transformers) ──────────────────
        embed_svc = get_embedding_service()
        embeddings = embed_svc.embed_batch([c["text"] for c in chunks])
        job.progress = 80
        db.commit()
        await _emit(job_id, {"status": "processing", "progress": 80, "step": "indexing"})

        # ── 7. Store in ChromaDB ─────────────────────────────────────────────
        vs = get_vector_store()
        chroma_chunks = [
            {
                "id": f"doc_{document_id}_chunk_{i}",
                "text": chunk["text"],
                "embedding": embedding,
                "metadata": {
                    **chunk.get("metadata", {}),
                    "doc_id": str(document_id),
                    "project_id": str(doc.project_id),
                },
            }
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
        ]
        vs.add_chunks(chroma_chunks)

        # ── 8. Mark completed ────────────────────────────────────────────────
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        job.progress = 100
        doc.status = "processed"
        doc.processed_at = datetime.utcnow()
        db.commit()

        await _emit(job_id, {
            "status": "completed", "progress": 100,
            "step": "done", "doc_type": doc_type, "chunks": len(chunks),
        })
        logger.info(
            "Job %d completed — document %d | type=%s | chunks=%d",
            job_id, document_id, doc_type, len(chunks),
        )

    except Exception as exc:
        logger.exception("Processing failed for job %d: %s", job_id, exc)
        try:
            job = db.get(ProcessingJob, job_id)
            doc = db.get(Document, document_id)
            if job:
                job.status = "failed"
                job.error_message = str(exc)
                job.completed_at = datetime.utcnow()
            if doc:
                doc.status = "error"
                doc.error_message = str(exc)
            db.commit()
        except Exception:
            pass
        await _emit(job_id, {"status": "failed", "error": str(exc)})
    finally:
        db.close()
