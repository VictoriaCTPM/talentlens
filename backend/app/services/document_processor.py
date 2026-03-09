"""
Document processor: single LLM call that classifies + extracts structured data.
Follows DEC-007 (batch classify+extract into 1 call).
"""
import json
import logging
from typing import Any

from pydantic import BaseModel, ValidationError

from app.services.llm.base import LLMProvider

logger = logging.getLogger(__name__)

# ── Extraction schemas ──────────────────────────────────────────────────────

class ResumeExtracted(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    skills: list[str] = []
    experience: list[dict[str, Any]] = []   # {company, role, duration, description}
    education: list[dict[str, Any]] = []    # {institution, degree, year}
    summary: str | None = None


class JDExtracted(BaseModel):
    title: str | None = None
    company: str | None = None
    department: str | None = None
    level: str | None = None               # junior/mid/senior/lead
    required_skills: list[str] = []
    nice_to_have_skills: list[str] = []
    responsibilities: list[str] = []
    requirements: list[str] = []


class WeeklyReportExtracted(BaseModel):
    developer_name: str | None = None
    project_name: str | None = None
    week_date: str | None = None
    tasks_completed: list[str] = []
    tasks_in_progress: list[str] = []
    blockers: list[str] = []
    hours_logged: float | None = None


class InterviewResultExtracted(BaseModel):
    candidate_name: str | None = None
    position: str | None = None
    interview_date: str | None = None
    interviewer: str | None = None
    technical_score: float | None = None   # 1-10
    communication_score: float | None = None  # 1-10
    verdict: str | None = None             # pass/fail/maybe
    notes: str | None = None
    strengths: list[str] = []
    weaknesses: list[str] = []


_SCHEMA_MAP: dict[str, type[BaseModel]] = {
    "resume": ResumeExtracted,
    "jd": JDExtracted,
    "report": WeeklyReportExtracted,
    "interview": InterviewResultExtracted,
    "job_request": JDExtracted,       # same shape as JD
    "client_report": WeeklyReportExtracted,  # similar shape
}

_DOC_TYPES = list(_SCHEMA_MAP.keys())

# ── Prompts ─────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a document analysis assistant for a recruiting firm.
Your job is to classify documents and extract structured data from them.
Always respond with valid JSON only — no markdown, no explanations."""

def _build_prompt(text: str, filename: str, error_feedback: str = "") -> str:
    schema_hint = json.dumps({k: v.model_fields for k, v in _SCHEMA_MAP.items()}, default=str, indent=2)
    error_section = f"\n\nPREVIOUS ATTEMPT FAILED WITH ERROR:\n{error_feedback}\nPlease fix the JSON." if error_feedback else ""

    # Truncate very long documents to stay within token limits
    max_chars = 8000
    truncated = text[:max_chars] + ("\n[... truncated ...]" if len(text) > max_chars else "")

    return f"""Analyze this document and respond with JSON only.

FILENAME: {filename}

DOCUMENT TEXT:
{truncated}

TASK:
1. Classify the document as one of: {", ".join(_DOC_TYPES)}
2. Extract structured data from it.

RESPOND WITH THIS EXACT JSON STRUCTURE:
{{
  "doc_type": "<one of: {', '.join(_DOC_TYPES)}>",
  "extracted": {{
    <fields matching the doc_type schema below>
  }}
}}

SCHEMAS PER DOC TYPE:
- resume: name, email, phone, skills (list), experience (list of {{company, role, duration, description}}), education (list of {{institution, degree, year}}), summary
- jd / job_request: title, company, department, level (junior/mid/senior/lead), required_skills (list), nice_to_have_skills (list), responsibilities (list), requirements (list)
- report / client_report: developer_name, project_name, week_date, tasks_completed (list), tasks_in_progress (list), blockers (list), hours_logged (number or null)
- interview: candidate_name, position, interview_date, interviewer, technical_score (1-10), communication_score (1-10), verdict (pass/fail/maybe), notes, strengths (list), weaknesses (list)

Rules:
- Use null for missing fields, never omit keys.
- All list fields must be arrays even if empty.
- Do not add fields outside the schema.{error_section}"""


# ── Public API ───────────────────────────────────────────────────────────────

async def classify_and_extract(
    text: str,
    filename: str,
    llm_client: LLMProvider,
) -> dict[str, Any]:
    """
    Single LLM call: classify document type + extract structured data.

    Returns:
        {
            "doc_type": str,
            "extracted": dict,
            "raw_text": str,
        }

    Raises:
        ValueError: if both attempts fail to produce valid structured output.
    """
    raw_text = text
    error_feedback = ""

    for attempt in range(2):
        prompt = _build_prompt(text, filename, error_feedback)
        response = await llm_client.generate(
            prompt=prompt,
            system_prompt=_SYSTEM_PROMPT,
            temperature=0.0,
            max_tokens=2048,
        )

        try:
            data = _parse_json(response)
            doc_type = data.get("doc_type", "").lower().strip()
            extracted_raw = data.get("extracted", {})

            if doc_type not in _SCHEMA_MAP:
                raise ValueError(f"Unknown doc_type '{doc_type}'. Must be one of {_DOC_TYPES}")

            schema_cls = _SCHEMA_MAP[doc_type]
            extracted = schema_cls(**extracted_raw)

            return {
                "doc_type": doc_type,
                "extracted": extracted.model_dump(),
                "raw_text": raw_text,
            }

        except (ValidationError, ValueError, KeyError, json.JSONDecodeError) as exc:
            error_feedback = str(exc)
            logger.warning("classify_and_extract attempt %d failed: %s", attempt + 1, exc)
            if attempt == 1:
                raise ValueError(f"classify_and_extract failed after 2 attempts: {exc}") from exc

    raise RuntimeError("Unreachable")


# ── Chunking ─────────────────────────────────────────────────────────────────

_MAX_CHUNK_CHARS = 2000
_OVERLAP_CHARS = 100


def chunk_document(
    text: str,
    doc_type: str,
    extracted_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Split a document into chunks for vector indexing.
    Follows DEC-005: type-specific chunking strategy.

    Returns list of dicts: {id_suffix, text, metadata}.
    Caller must add the full unique id and embedding.
    """
    if doc_type == "resume":
        return _chunk_resume(text, extracted_data)
    elif doc_type in ("jd", "job_request"):
        return _chunk_single(text, doc_type, extracted_data)
    elif doc_type in ("report", "client_report"):
        return _chunk_report(text, extracted_data)
    elif doc_type == "interview":
        return _chunk_single(text, doc_type, extracted_data)
    else:
        return _chunk_single(text, doc_type, extracted_data)


def _base_meta(doc_type: str, extracted: dict) -> dict[str, Any]:
    """Common metadata fields extracted from any doc type."""
    meta: dict[str, Any] = {"doc_type": doc_type}
    # Person name — field varies by doc type
    meta["person_name"] = (
        extracted.get("name")
        or extracted.get("candidate_name")
        or extracted.get("developer_name")
        or ""
    )
    meta["date"] = (
        extracted.get("week_date")
        or extracted.get("interview_date")
        or ""
    )
    return meta


def _chunk_resume(text: str, extracted: dict) -> list[dict[str, Any]]:
    chunks = []
    meta = _base_meta("resume", extracted)
    meta["skills"] = extracted.get("skills", [])

    # One chunk per experience entry
    for i, exp in enumerate(extracted.get("experience", [])):
        chunk_text = (
            f"Experience at {exp.get('company', '')} as {exp.get('role', '')} "
            f"({exp.get('duration', '')}):\n{exp.get('description', '')}"
        )
        chunks.append({"section": f"experience_{i}", "text": chunk_text.strip(), "metadata": {**meta, "section": "experience"}})

    # Skills chunk
    skills = extracted.get("skills", [])
    if skills:
        chunks.append({
            "section": "skills",
            "text": f"Skills: {', '.join(skills)}",
            "metadata": {**meta, "section": "skills"},
        })

    # Education chunk
    for i, edu in enumerate(extracted.get("education", [])):
        chunk_text = (
            f"Education: {edu.get('degree', '')} at {edu.get('institution', '')} "
            f"({edu.get('year', '')})"
        )
        chunks.append({"section": f"education_{i}", "text": chunk_text.strip(), "metadata": {**meta, "section": "education"}})

    # Summary chunk
    summary = extracted.get("summary") or ""
    if summary:
        chunks.append({"section": "summary", "text": summary, "metadata": {**meta, "section": "summary"}})

    # Fallback: if nothing was extracted, chunk the raw text
    if not chunks:
        chunks = _sliding_window(text, doc_type="resume", meta=meta)

    return chunks


def _chunk_report(text: str, extracted: dict) -> list[dict[str, Any]]:
    chunks = []
    meta = _base_meta("report", extracted)

    completed = extracted.get("tasks_completed", [])
    in_progress = extracted.get("tasks_in_progress", [])
    blockers = extracted.get("blockers", [])

    if completed:
        chunks.append({
            "section": "completed",
            "text": "Tasks completed:\n" + "\n".join(f"- {t}" for t in completed),
            "metadata": {**meta, "section": "completed"},
        })
    if in_progress:
        chunks.append({
            "section": "in_progress",
            "text": "Tasks in progress:\n" + "\n".join(f"- {t}" for t in in_progress),
            "metadata": {**meta, "section": "in_progress"},
        })
    if blockers:
        chunks.append({
            "section": "blockers",
            "text": "Blockers:\n" + "\n".join(f"- {t}" for t in blockers),
            "metadata": {**meta, "section": "blockers"},
        })

    if not chunks:
        chunks = _sliding_window(text, doc_type="report", meta=meta)

    return chunks


def _chunk_single(text: str, doc_type: str, extracted: dict) -> list[dict[str, Any]]:
    """Single chunk or sliding window if text is too long."""
    meta = _base_meta(doc_type, extracted)
    if doc_type in ("jd", "job_request"):
        skills = extracted.get("required_skills", []) + extracted.get("nice_to_have_skills", [])
        meta["skills"] = skills

    if len(text) <= _MAX_CHUNK_CHARS:
        return [{"section": "full", "text": text, "metadata": {**meta, "section": "full"}}]
    return _sliding_window(text, doc_type=doc_type, meta=meta)


def _sliding_window(text: str, doc_type: str, meta: dict) -> list[dict[str, Any]]:
    """Fall-back: sliding window with overlap."""
    chunks = []
    start = 0
    idx = 0
    while start < len(text):
        end = start + _MAX_CHUNK_CHARS
        chunk_text = text[start:end]
        chunks.append({
            "section": f"chunk_{idx}",
            "text": chunk_text,
            "metadata": {**meta, "section": f"chunk_{idx}"},
        })
        start = end - _OVERLAP_CHARS
        idx += 1
    return chunks


def _parse_json(text: str) -> dict:
    """Extract JSON from LLM response, tolerating markdown code fences."""
    text = text.strip()
    # Strip ```json ... ``` fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        # Remove first and last fence lines
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner).strip()
    return json.loads(text)
