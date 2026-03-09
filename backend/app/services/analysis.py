"""
AI Analysis Engine — 4 modes (A/B/C/D).
Follows DEC-007 (1 LLM call per mode) and DEC-008 (5-level anti-hallucination).
"""
import json
import logging
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ValidationError

from app.services.llm.base import LLMProvider
from app.services.retrieval import RetrievalService

logger = logging.getLogger(__name__)

_PROMPT_VERSION = "1.0"

# ── Anti-hallucination boilerplate injected into every prompt ────────────────
_GROUNDING = """CRITICAL RULES:
1. Base your analysis ONLY on the provided documents. Do not invent facts.
2. Cite the specific [Source N] for every claim you make.
3. If the documents lack enough information, say so explicitly — do not guess.
4. Rate your confidence: LOW (little data), MEDIUM (some data), HIGH (strong data).
5. Respond with valid JSON only — no markdown, no explanations outside JSON."""

_SYSTEM_PROMPT = (
    "You are an expert recruiting analyst for a talent intelligence platform. "
    "You analyze historical project data and job descriptions to give hiring guidance. "
    + _GROUNDING
)


# ── Output Pydantic schemas ───────────────────────────────────────────────────

class SkillInfo(BaseModel):
    name: str
    criticality: str = "must"           # must / nice
    market_availability: str = "moderate"  # easy / moderate / hard


class TalentBriefResult(BaseModel):
    skills_required: list[SkillInfo] = []
    search_guidance: list[str] = []
    historical_insights: list[str] = []
    pitfalls: list[str] = []
    estimated_time_to_fill_days: int | None = None
    confidence: float = 0.5
    confidence_level: str = "MEDIUM"        # LOW / MEDIUM / HIGH
    confidence_explanation: str = ""
    sources: list[str] = []


class HistoricalPosition(BaseModel):
    project: str | None = None
    role: str | None = None
    outcome: str | None = None
    time_to_fill: int | None = None
    key_learnings: str | None = None


class HistoricalMatchResult(BaseModel):
    similar_positions: list[HistoricalPosition] = []
    success_patterns: list[str] = []
    failure_patterns: list[str] = []
    confidence: float = 0.5
    confidence_level: str = "MEDIUM"
    confidence_explanation: str = ""
    sources: list[str] = []


class LevelEvidence(BaseModel):
    project: str | None = None
    role: str | None = None
    level: str | None = None
    outcome: str | None = None


class LevelAdvisorResult(BaseModel):
    recommended_level: str = "mid"       # junior / mid / senior / lead
    reasoning: str = ""
    evidence: list[LevelEvidence] = []
    risk_of_wrong_level: str = ""
    confidence: float = 0.5
    confidence_level: str = "MEDIUM"
    confidence_explanation: str = ""
    sources: list[str] = []


class SkillMatchDetail(BaseModel):
    score: int = 0
    matched: list[str] = []
    missing: list[str] = []
    partial: list[str] = []


class ExperienceMatch(BaseModel):
    score: int = 0
    relevant_years: int | None = None
    notes: str = ""


class TeamCompatibility(BaseModel):
    score: int = 0
    notes: str = ""


class HistoricalComparison(BaseModel):
    similar_hire: str | None = None
    project: str | None = None
    outcome: str | None = None


class CandidateScoreResult(BaseModel):
    overall_score: int = 0              # 0-100
    verdict: str = "not_recommended"    # strong_fit / moderate_fit / risky / not_recommended
    skill_match: SkillMatchDetail = SkillMatchDetail()
    experience_match: ExperienceMatch = ExperienceMatch()
    team_compatibility: TeamCompatibility = TeamCompatibility()
    strengths: list[str] = []
    gaps: list[str] = []
    historical_comparison: HistoricalComparison = HistoricalComparison()
    confidence: float = 0.5
    confidence_level: str = "MEDIUM"
    confidence_explanation: str = ""
    sources: list[str] = []


_SCHEMA_MAP: dict[str, type[BaseModel]] = {
    "A": TalentBriefResult,
    "B": HistoricalMatchResult,
    "C": LevelAdvisorResult,
    "D": CandidateScoreResult,
}


# ── Data sufficiency check ────────────────────────────────────────────────────

def data_sufficiency_check(project_id: int, mode: str) -> dict[str, Any]:
    """
    Check whether a project has enough documents to run the requested analysis mode.
    Returns {can_run, missing, data_quality}.
    """
    from app.models.database import Document, SessionLocal

    db = SessionLocal()
    try:
        docs = (
            db.query(Document)
            .filter_by(project_id=project_id, status="processed")
            .all()
        )
    finally:
        db.close()

    types = [d.doc_type for d in docs if d.doc_type]
    jd_count       = types.count("jd") + types.count("job_request")
    resume_count   = types.count("resume")
    report_count   = types.count("report") + types.count("client_report")
    interview_count = types.count("interview")
    total          = len(types)

    if mode == "A":
        if jd_count == 0:
            return {"can_run": False, "missing": ["At least 1 job description required"], "data_quality": "insufficient"}
        quality = "high" if report_count >= 2 or total >= 5 else "medium" if report_count >= 1 or total >= 2 else "low"
        return {"can_run": True, "missing": [], "data_quality": quality}

    elif mode == "B":
        missing = []
        if jd_count < 1:
            missing.append("At least 1 job description required")
        if jd_count < 3 and report_count < 2:
            missing.append(f"More historical data recommended (have {total} docs, ideally 5+)")
        quality = "insufficient" if total == 0 else "low" if total < 3 else "medium" if total < 6 else "high"
        return {"can_run": jd_count >= 1, "missing": missing, "data_quality": quality}

    elif mode == "C":
        missing = []
        if jd_count < 1:
            missing.append("At least 1 job description required")
        if report_count < 2:
            missing.append(f"Need 2+ project reports for level evidence (have {report_count})")
        quality = "insufficient" if jd_count == 0 else "low" if report_count < 1 else "medium" if report_count < 3 else "high"
        return {"can_run": jd_count >= 1, "missing": missing, "data_quality": quality}

    elif mode == "D":
        missing = []
        if resume_count == 0:
            missing.append("At least 1 resume required")
        if jd_count == 0:
            missing.append("At least 1 job description required")
        quality = "high" if report_count >= 2 and interview_count >= 1 else "medium" if report_count >= 1 else "low"
        return {
            "can_run": resume_count >= 1 and jd_count >= 1,
            "missing": missing,
            "data_quality": quality,
        }

    return {"can_run": False, "missing": [f"Unknown mode: {mode}"], "data_quality": "insufficient"}


# ── Main analysis engine ──────────────────────────────────────────────────────

class AnalysisEngine:

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm
        self._retrieval = RetrievalService()

    # ── Mode A — Talent Brief ─────────────────────────────────────────────────

    async def talent_brief(self, jd_document_id: int) -> dict[str, Any]:
        """
        Given a JD, produce a talent brief: skills, search tips, historical
        insights, pitfalls, and time-to-fill estimate.
        """
        jd_data, project_id = self._load_extracted(jd_document_id)

        context = self._retrieval.get_context_for_analysis(
            query=f"job description {jd_data.get('title', '')} skills {' '.join(jd_data.get('required_skills', []))}",
            project_id=str(project_id),
            doc_types=["jd", "job_request", "report", "interview"],
            max_tokens=5000,
        )

        prompt = f"""You are analyzing a job description to produce a Talent Brief.

JOB DESCRIPTION DATA:
{json.dumps(jd_data, indent=2)}

HISTORICAL CONTEXT FROM PROJECT DOCUMENTS:
{context}

{_GROUNDING}

Produce a JSON Talent Brief with this exact structure:
{{
  "skills_required": [
    {{"name": "skill name", "criticality": "must|nice", "market_availability": "easy|moderate|hard"}}
  ],
  "search_guidance": ["tip 1", "tip 2"],
  "historical_insights": ["insight from documents [Source N]"],
  "pitfalls": ["common mistake to avoid"],
  "estimated_time_to_fill_days": 30,
  "confidence": 0.75,
  "confidence_level": "HIGH|MEDIUM|LOW",
  "confidence_explanation": "Explain what data supports this confidence",
  "sources": ["Source 1 description", "Source 2 description"]
}}

Rules:
- skills_required must cover all required_skills from the JD
- historical_insights must cite [Source N] from context; if no history, say "No historical data available"
- confidence reflects how much historical data supports the analysis
- All lists must be arrays even if empty. Numbers must be numbers not strings."""

        result = await self._call_with_validation(prompt, "A")
        return self._save_and_return(
            mode="A",
            project_id=project_id,
            input_doc_ids=[jd_document_id],
            result=result,
        )

    # ── Mode B — Historical Match ─────────────────────────────────────────────

    async def historical_match(self, jd_document_id: int) -> dict[str, Any]:
        """
        Find similar past positions and extract success/failure patterns.
        """
        jd_data, project_id = self._load_extracted(jd_document_id)

        context = self._retrieval.get_context_for_analysis(
            query=f"similar role {jd_data.get('title', '')} outcomes results performance",
            project_id=str(project_id),
            max_tokens=6000,
        )

        prompt = f"""You are analyzing historical project documents to find similar past positions.

JOB DESCRIPTION:
{json.dumps(jd_data, indent=2)}

HISTORICAL DOCUMENTS:
{context}

{_GROUNDING}

Respond with JSON:
{{
  "similar_positions": [
    {{
      "project": "project name from documents",
      "role": "role title",
      "outcome": "what happened — successful/not/why",
      "time_to_fill": 45,
      "key_learnings": "specific lesson [Source N]"
    }}
  ],
  "success_patterns": ["pattern observed in successful hires [Source N]"],
  "failure_patterns": ["what went wrong in unsuccessful cases [Source N]"],
  "confidence": 0.6,
  "confidence_level": "HIGH|MEDIUM|LOW",
  "confidence_explanation": "how much historical data was available",
  "sources": ["description of source documents used"]
}}

If insufficient historical data exists, return empty arrays and LOW confidence with explanation."""

        result = await self._call_with_validation(prompt, "B")
        return self._save_and_return(
            mode="B",
            project_id=project_id,
            input_doc_ids=[jd_document_id],
            result=result,
        )

    # ── Mode C — Level Advisor ────────────────────────────────────────────────

    async def level_advisor(self, jd_document_id: int) -> dict[str, Any]:
        """
        Recommend the right seniority level for this role based on historical evidence.
        """
        jd_data, project_id = self._load_extracted(jd_document_id)

        context = self._retrieval.get_context_for_analysis(
            query=f"seniority level experience years {jd_data.get('title', '')} senior junior mid",
            project_id=str(project_id),
            doc_types=["jd", "job_request", "report", "interview", "resume"],
            max_tokens=5000,
        )

        prompt = f"""You are advising on the correct seniority level for a role.

JOB DESCRIPTION:
{json.dumps(jd_data, indent=2)}

HISTORICAL EVIDENCE:
{context}

{_GROUNDING}

Respond with JSON:
{{
  "recommended_level": "junior|mid|senior|lead",
  "reasoning": "clear explanation citing evidence [Source N]",
  "evidence": [
    {{
      "project": "project name",
      "role": "role",
      "level": "senior/mid/junior",
      "outcome": "how that level worked out"
    }}
  ],
  "risk_of_wrong_level": "what happens if you hire too junior or too senior",
  "confidence": 0.7,
  "confidence_level": "HIGH|MEDIUM|LOW",
  "confidence_explanation": "basis for confidence",
  "sources": ["source descriptions"]
}}"""

        result = await self._call_with_validation(prompt, "C")
        return self._save_and_return(
            mode="C",
            project_id=project_id,
            input_doc_ids=[jd_document_id],
            result=result,
        )

    # ── Mode D — Candidate Scorer ─────────────────────────────────────────────

    async def candidate_score(
        self, resume_document_id: int, jd_document_id: int
    ) -> dict[str, Any]:
        """
        Score a candidate (resume) against a job description, with historical comparison.
        """
        resume_data, resume_project_id = self._load_extracted(resume_document_id)
        jd_data, jd_project_id = self._load_extracted(jd_document_id)
        project_id = jd_project_id  # use the JD's project as the main project

        candidate_name = resume_data.get("name") or "the candidate"
        jd_title = jd_data.get("title") or "this role"

        context = self._retrieval.get_context_for_analysis(
            query=f"similar candidate performance outcome {jd_title} experience skills",
            project_id=str(project_id),
            doc_types=["resume", "interview", "report"],
            max_tokens=5000,
        )

        prompt = f"""You are scoring a candidate against a job description.

CANDIDATE RESUME:
{json.dumps(resume_data, indent=2)}

JOB DESCRIPTION:
{json.dumps(jd_data, indent=2)}

HISTORICAL CONTEXT (similar hires, past outcomes):
{context}

{_GROUNDING}

Score {candidate_name} for {jd_title}. Respond with JSON:
{{
  "overall_score": 72,
  "verdict": "strong_fit|moderate_fit|risky|not_recommended",
  "skill_match": {{
    "score": 80,
    "matched": ["Python", "FastAPI"],
    "missing": ["Kubernetes"],
    "partial": ["AWS — has experience but not deep"]
  }},
  "experience_match": {{
    "score": 75,
    "relevant_years": 5,
    "notes": "relevant experience explanation [Source N]"
  }},
  "team_compatibility": {{
    "score": 70,
    "notes": "cultural/team fit assessment based on documents"
  }},
  "strengths": ["concrete strength 1", "strength 2"],
  "gaps": ["gap 1 — why it matters for this role"],
  "historical_comparison": {{
    "similar_hire": "name or description from documents",
    "project": "project name",
    "outcome": "what happened with that hire [Source N]"
  }},
  "confidence": 0.8,
  "confidence_level": "HIGH|MEDIUM|LOW",
  "confidence_explanation": "basis for confidence",
  "sources": ["source descriptions"]
}}

Verdicts: strong_fit (85+), moderate_fit (65-84), risky (45-64), not_recommended (<45).
All scores are 0-100 integers."""

        result = await self._call_with_validation(prompt, "D")
        return self._save_and_return(
            mode="D",
            project_id=project_id,
            input_doc_ids=[resume_document_id, jd_document_id],
            result=result,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _load_extracted(self, document_id: int) -> tuple[dict[str, Any], int]:
        """Load extracted structured data for a document. Returns (data, project_id)."""
        from app.models.database import Document, ExtractedData, SessionLocal

        db = SessionLocal()
        try:
            doc = db.get(Document, document_id)
            if not doc:
                raise ValueError(f"Document {document_id} not found")
            if doc.status != "processed":
                raise ValueError(f"Document {document_id} is not processed yet (status={doc.status})")

            ed = (
                db.query(ExtractedData)
                .filter_by(document_id=document_id)
                .order_by(ExtractedData.id.desc())
                .first()
            )
            if not ed:
                raise ValueError(f"No extracted data for document {document_id}")

            return ed.structured_data, doc.project_id
        finally:
            db.close()

    async def _call_with_validation(
        self, prompt: str, mode: str, error_feedback: str = ""
    ) -> dict[str, Any]:
        """Call LLM, parse JSON, validate with Pydantic. Retry once on failure."""
        schema_cls = _SCHEMA_MAP[mode]

        full_prompt = prompt
        if error_feedback:
            full_prompt += f"\n\nPREVIOUS ATTEMPT FAILED: {error_feedback}\nPlease fix and return valid JSON."

        for attempt in range(2):
            response = await self._llm.generate(
                prompt=full_prompt,
                system_prompt=_SYSTEM_PROMPT,
                temperature=0.1,
                max_tokens=2048,
            )
            try:
                raw = _parse_json(response)
                validated = schema_cls(**raw)
                return validated.model_dump()
            except (ValidationError, ValueError, json.JSONDecodeError) as exc:
                logger.warning("Analysis mode %s attempt %d failed: %s", mode, attempt + 1, exc)
                if attempt == 0:
                    full_prompt = prompt + f"\n\nPREVIOUS ATTEMPT FAILED: {exc}\nPlease fix and return valid JSON."
                else:
                    raise ValueError(f"Analysis mode {mode} failed after 2 attempts: {exc}") from exc

        raise RuntimeError("Unreachable")

    def _save_and_return(
        self,
        mode: str,
        project_id: int,
        input_doc_ids: list[int],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        """Save result to AnalysisResult table and return enriched response."""
        from app.models.database import AnalysisResult, SessionLocal

        db = SessionLocal()
        try:
            ar = AnalysisResult(
                project_id=project_id,
                analysis_mode=mode,
                input_document_ids=input_doc_ids,
                result_data=result,
                confidence_score=result.get("confidence"),
                source_citations=result.get("sources"),
                model_used=self._llm.model_name,
                prompt_version=_PROMPT_VERSION,
            )
            db.add(ar)
            db.commit()
            db.refresh(ar)
            result_id = ar.id
        finally:
            db.close()

        logger.info(
            "Analysis mode=%s saved as result_id=%d project=%d confidence=%s",
            mode, result_id, project_id, result.get("confidence_level"),
        )
        return {
            "result_id": result_id,
            "mode": mode,
            "project_id": project_id,
            "input_document_ids": input_doc_ids,
            **result,
        }


# ── JSON parsing helper ───────────────────────────────────────────────────────

def _parse_json(text: str) -> dict:
    """Strip markdown fences and parse JSON."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner).strip()
    return json.loads(text)


def get_analysis_engine(llm: LLMProvider | None = None) -> AnalysisEngine:
    if llm is None:
        from app.services.llm.client import get_llm_client
        llm = get_llm_client()
    return AnalysisEngine(llm)
