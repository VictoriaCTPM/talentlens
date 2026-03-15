"""
AI Analysis Engine — 4 modes (A/B/C/D).
Follows DEC-007 (1 LLM call per mode) and DEC-008 (5-level anti-hallucination).
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, ValidationError, model_validator

from app.services.context_cache import context_cache
from app.services.llm.base import LLMProvider
from app.services.retrieval import RetrievalService
from app.services.team_context import TeamContextService
from app.utils.json_helpers import parse_llm_json

logger = logging.getLogger(__name__)

_PROMPT_VERSION = "1.0"

# Token budget per mode — must fit within 12K TPM total (input + output)
_MAX_TOKENS_MAP: dict[str, int] = {
    "A": 2048,
    "B": 2048,
    "C": 1536,
    "D": 2048,
    "E": 2560,
    "PI": 4096,  # 3 analyses combined
}

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


class KeyArgument(BaseModel):
    point: str
    evidence: str
    impact: str = "neutral"  # positive / negative / neutral


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
    reasoning: str = ""
    key_arguments: list[KeyArgument] = []


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
    reasoning: str = ""
    key_arguments: list[KeyArgument] = []


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
    key_arguments: list[KeyArgument] = []


class MustHaveSkillMatch(BaseModel):
    skill: str
    match_level: str = "none"   # hands_on / exposure / none
    evidence: str = ""


class SkillMatchDetail(BaseModel):
    score: int = 0
    must_have_skills: list[MustHaveSkillMatch] = []
    matched: list[str] = []
    missing: list[str] = []
    partial: list[str] = []


class ExperienceMatch(BaseModel):
    score: int = 0
    relevant_years: float | None = None
    required_years: float | None = None
    role_type_match: bool = True
    notes: str = ""


class RoleAlignment(BaseModel):
    candidate_role_type: str = "unknown"
    jd_role_type: str = "unknown"
    is_match: bool = False
    role_alignment_score: int = 10
    score_capped: bool = False
    note: str = ""


class DomainMatch(BaseModel):
    score: int = 0
    industry_match: bool = False
    relevant_knowledge: list[str] = []


class SoftSkillsBreakdown(BaseModel):
    score: int = 0
    communication: int = 0
    collaboration: int = 0
    problem_solving: int = 0


class ScoreBreakdown(BaseModel):
    hard_skills_weighted: float = 0.0
    experience_weighted: float = 0.0
    domain_weighted: float = 0.0
    soft_skills_weighted: float = 0.0
    team_weighted: float = 0.0
    raw_total: float = 0.0
    role_cap_applied: bool = False
    final_score: int = 0


class TeamCompatibility(BaseModel):
    score: int = 0
    notes: str = ""


class TeamComplementarity(BaseModel):
    score: int = 0
    fills_gaps: list[str] = []
    overlaps: list[str] = []
    team_dynamics: str = ""
    recommendation: str = ""


class HistoricalComparison(BaseModel):
    similar_hire: str | None = None
    project: str | None = None
    outcome: str | None = None


class CandidateScoreResult(BaseModel):
    overall_score: int = 0              # 0-100
    verdict: str = "not_recommended"    # strong_fit / moderate_fit / risky / not_recommended
    role_alignment: RoleAlignment = RoleAlignment()
    skill_match: SkillMatchDetail = SkillMatchDetail()
    experience_match: ExperienceMatch = ExperienceMatch()
    domain_match: DomainMatch = DomainMatch()
    soft_skills: SoftSkillsBreakdown = SoftSkillsBreakdown()
    team_compatibility: TeamCompatibility = TeamCompatibility()
    team_complementarity: TeamComplementarity = TeamComplementarity()
    score_breakdown: ScoreBreakdown = ScoreBreakdown()
    strengths: list[str] = []
    gaps: list[str] = []
    historical_comparison: HistoricalComparison = HistoricalComparison()
    confidence: float = 0.5
    confidence_level: str = "MEDIUM"
    confidence_explanation: str = ""
    sources: list[str] = []
    reasoning: str = ""
    key_arguments: list[KeyArgument] = []
    data_sources_used: list[str] = []

    @model_validator(mode="after")
    def enforce_verdict_score_consistency(self) -> "CandidateScoreResult":
        """Enforce verdict matches score AND role alignment."""
        # Role alignment override: if role mismatch, force not_recommended and cap score
        if self.role_alignment.role_alignment_score < 50:
            if self.overall_score > 35:
                logger.info(
                    "Role cap applied: score %d → 35 (candidate=%s, jd=%s)",
                    self.overall_score, self.role_alignment.candidate_role_type,
                    self.role_alignment.jd_role_type,
                )
                self.overall_score = min(self.overall_score, 35)
            self.verdict = "not_recommended"
            self.role_alignment.score_capped = True
            return self

        # Standard verdict check
        score = self.overall_score
        expected = (
            "strong_fit" if score >= 85
            else "moderate_fit" if score >= 65
            else "risky" if score >= 45
            else "not_recommended"
        )
        if self.verdict != expected:
            logger.info(
                "Corrected verdict: LLM said '%s' for score %d, should be '%s'",
                self.verdict, score, expected,
            )
            self.verdict = expected
        return self


# ── Mode E — JD Reality Check schemas ────────────────────────────────────────

class SkillsVsReality(BaseModel):
    jd_requires: list[str] = []
    team_already_has: list[str] = []
    actually_needed: list[str] = []
    questionable_requirements: list[str] = []


class WorkloadAnalysis(BaseModel):
    jd_claims: str = ""
    report_reality: str = ""
    mismatches: list[str] = []
    is_jd_accurate: bool = True


class NecessityCheck(BaseModel):
    is_hire_justified: bool = True
    reasoning: str = ""
    alternative_suggestions: list[str] = []
    priority: str = "medium"   # critical / high / medium / low


class JDRealityCheckResult(BaseModel):
    skills_vs_reality: SkillsVsReality = SkillsVsReality()
    workload_analysis: WorkloadAnalysis = WorkloadAnalysis()
    necessity_check: NecessityCheck = NecessityCheck()
    jd_improvement_suggestions: list[str] = []
    confidence: float = 0.5
    confidence_level: str = "MEDIUM"
    confidence_explanation: str = ""
    sources: list[str] = []
    reasoning: str = ""
    key_arguments: list[KeyArgument] = []


# ── Position Intelligence (merged A+B+C) schema ───────────────────────────────

class PositionIntelligenceResult(BaseModel):
    talent_brief: TalentBriefResult = TalentBriefResult()
    historical_match: HistoricalMatchResult = HistoricalMatchResult()
    level_advisor: LevelAdvisorResult = LevelAdvisorResult()
    overall_confidence: float = 0.5
    reasoning: str = ""
    key_arguments: list[KeyArgument] = []


# ── Batch candidate scoring schemas ───────────────────────────────────────────

class BatchCandidateScoreItem(BaseModel):
    candidate_id: int | str  # LLM may return string; resolved after parsing
    overall_score: int = 0
    verdict: str = "not_recommended"
    role_alignment: RoleAlignment = RoleAlignment()
    skill_match: SkillMatchDetail = SkillMatchDetail()
    experience_match: ExperienceMatch = ExperienceMatch()
    domain_match: DomainMatch = DomainMatch()
    soft_skills: SoftSkillsBreakdown = SoftSkillsBreakdown()
    team_compatibility: TeamCompatibility = TeamCompatibility()
    team_complementarity: TeamComplementarity = TeamComplementarity()
    score_breakdown: ScoreBreakdown = ScoreBreakdown()
    strengths: list[str] = []
    gaps: list[str] = []
    historical_comparison: HistoricalComparison = HistoricalComparison()
    confidence: float = 0.5
    confidence_level: str = "MEDIUM"
    confidence_explanation: str = ""
    sources: list[str] = []
    reasoning: str = ""
    key_arguments: list[KeyArgument] = []

    @model_validator(mode="after")
    def enforce_verdict_score_consistency(self) -> "BatchCandidateScoreItem":
        # Role alignment override
        if self.role_alignment.role_alignment_score < 50:
            if self.overall_score > 35:
                logger.info(
                    "Batch role cap: score %d → 35 (candidate=%s, jd=%s)",
                    self.overall_score, self.role_alignment.candidate_role_type,
                    self.role_alignment.jd_role_type,
                )
                self.overall_score = min(self.overall_score, 35)
            self.verdict = "not_recommended"
            self.role_alignment.score_capped = True
            return self

        score = self.overall_score
        expected = (
            "strong_fit" if score >= 85
            else "moderate_fit" if score >= 65
            else "risky" if score >= 45
            else "not_recommended"
        )
        if self.verdict != expected:
            logger.info(
                "Batch: corrected verdict '%s' → '%s' for score %d",
                self.verdict, expected, score,
            )
            self.verdict = expected
        return self


class BatchScoringResult(BaseModel):
    candidates: list[BatchCandidateScoreItem] = []


_SCHEMA_MAP: dict[str, type[BaseModel]] = {
    "A": TalentBriefResult,
    "B": HistoricalMatchResult,
    "C": LevelAdvisorResult,
    "D": CandidateScoreResult,
    "E": JDRealityCheckResult,
    "PI": PositionIntelligenceResult,
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

    elif mode == "E":
        missing = []
        if jd_count == 0:
            missing.append("At least 1 job description required")
        quality = "high" if report_count >= 2 else "medium" if report_count >= 1 else "low"
        return {"can_run": jd_count >= 1, "missing": missing, "data_quality": quality}

    return {"can_run": False, "missing": [f"Unknown mode: {mode}"], "data_quality": "insufficient"}


# ── Main analysis engine ──────────────────────────────────────────────────────

class AnalysisEngine:

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm
        self._retrieval = RetrievalService()
        self._team_ctx = TeamContextService()

    def _team_context(self, project_id: int) -> str:
        """Return team context string, served from 5-min cache when available."""
        cached = context_cache.get(project_id, "team")
        if cached is not None:
            return cached
        value = self._team_ctx.get_team_context(project_id)
        # Cap to ~1500 tokens (~6000 chars) to stay within 12K TPM budget
        if len(value) > 6000:
            value = value[:6000] + "\n[... team context truncated for token budget ...]"
        context_cache.set(project_id, "team", value)
        return value

    def _reports_context(self, project_id: int) -> str:
        """Return reports context string, served from 5-min cache when available."""
        cached = context_cache.get(project_id, "reports")
        if cached is not None:
            return cached
        value = self._team_ctx.get_reports_context(project_id)
        # Cap to ~1500 tokens (~6000 chars) to stay within 12K TPM budget
        if len(value) > 6000:
            value = value[:6000] + "\n[... reports context truncated for token budget ...]"
        context_cache.set(project_id, "reports", value)
        return value

    def _rejection_patterns(self, project_id: int) -> str:
        """Return rejection patterns string, served from 5-min cache."""
        cached = context_cache.get(project_id, "rejections")
        if cached is not None:
            return cached
        value = self._team_ctx.get_rejection_patterns(project_id)
        if len(value) > 4000:
            value = value[:4000] + "\n[... truncated]"
        context_cache.set(project_id, "rejections", value)
        return value

    @staticmethod
    def _build_retrieval_query(
        mode: str,
        jd_text: str,
        candidate_name: str = "",
    ) -> str:
        """
        Return a retrieval query string tailored to the analysis mode.
        Focused queries surface more relevant chunks than generic JD text.
        """
        snippet = jd_text[:500]
        if mode == "position_intelligence":
            return f"hiring requirements skills experience outcomes seniority history for: {snippet}"
        elif mode == "candidate_score":
            prefix = f"candidate evaluation {candidate_name} " if candidate_name else "candidate evaluation "
            return f"{prefix}skills match performance fit for: {jd_text[:300]}"
        elif mode == "jd_reality_check":
            return f"actual work performed team responsibilities deliverables for: {jd_text[:300]}"
        else:
            return snippet

    # ── Mode A — Talent Brief ─────────────────────────────────────────────────

    async def talent_brief(self, jd_document_id: int) -> dict[str, Any]:
        """
        Given a JD, produce a talent brief.
        Uses cached result if run within 1 hour; otherwise triggers position_intelligence
        (single LLM call for A+B+C) and returns the A portion.
        """
        cached = self._get_cached_mode_result(jd_document_id, "A")
        if cached:
            logger.info("Cache hit for mode A, jd_doc=%d", jd_document_id)
            return cached
        a_result, _b, _c = await self._run_position_intelligence(jd_document_id)
        return a_result

    # ── Mode B — Historical Match ─────────────────────────────────────────────

    async def historical_match(self, jd_document_id: int) -> dict[str, Any]:
        """
        Find similar past positions and extract success/failure patterns.
        Uses cached result if run within 1 hour; otherwise triggers position_intelligence.
        """
        cached = self._get_cached_mode_result(jd_document_id, "B")
        if cached:
            logger.info("Cache hit for mode B, jd_doc=%d", jd_document_id)
            return cached
        _a, b_result, _c = await self._run_position_intelligence(jd_document_id)
        return b_result

    # ── Mode C — Level Advisor ────────────────────────────────────────────────

    async def level_advisor(self, jd_document_id: int) -> dict[str, Any]:
        """
        Recommend the right seniority level for this role based on historical evidence.
        Uses cached result if run within 1 hour; otherwise triggers position_intelligence.
        """
        cached = self._get_cached_mode_result(jd_document_id, "C")
        if cached:
            logger.info("Cache hit for mode C, jd_doc=%d", jd_document_id)
            return cached
        _a, _b, c_result = await self._run_position_intelligence(jd_document_id)
        return c_result

    # ── Position Intelligence (merged A+B+C) ──────────────────────────────────
    # NOTE: position_intelligence() and _run_position_intelligence() are not yet
    # wired to the frontend. The frontend calls A/B/C modes separately.
    # Plan: switch frontend to use /api/analysis/position-intelligence endpoint
    # to save ~67% tokens. See docs/DeadCodeAudit.md.

    async def position_intelligence(self, jd_document_id: int) -> dict[str, Any]:
        """
        Return all three position analyses (A+B+C) in one response.
        Serves cached results if all three exist within the last hour;
        otherwise runs a single merged LLM call and populates the cache.
        """
        a = self._get_cached_mode_result(jd_document_id, "A")
        b = self._get_cached_mode_result(jd_document_id, "B")
        c = self._get_cached_mode_result(jd_document_id, "C")
        if a and b and c:
            logger.info("Full PI cache hit, jd_doc=%d", jd_document_id)
            return {"talent_brief": a, "historical_match": b, "level_advisor": c}
        a, b, c = await self._run_position_intelligence(jd_document_id)
        return {"talent_brief": a, "historical_match": b, "level_advisor": c}

    async def _run_position_intelligence(
        self, jd_document_id: int
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        """
        Single LLM call producing Modes A+B+C simultaneously.
        Saves three AnalysisResult rows and returns (a_result, b_result, c_result).
        Token saving: ~8 000 tokens vs ~16 000 for three separate calls.
        """
        jd_data, project_id = self._load_extracted(jd_document_id)

        context = self._retrieval.get_context_for_analysis(
            query=self._build_retrieval_query(
                "position_intelligence",
                jd_text=str(jd_data),
            ),
            project_id=str(project_id),
            doc_types=["jd", "job_request", "report", "interview", "resume"],
            max_tokens=3000,
        )
        team_context = self._team_context(project_id)
        rejection_patterns = self._rejection_patterns(project_id)
        team_section = (
            f"\nCURRENT PROJECT TEAM:\n{team_context}" if team_context else ""
        )
        rejection_section = (
            f"\n\nHISTORICAL REJECTION PATTERNS:\n{rejection_patterns}" if rejection_patterns else ""
        )

        prompt = f"""You are a senior hiring consultant. Produce THREE simultaneous analyses for this job description in one JSON response.

JOB DESCRIPTION DATA:
{json.dumps(jd_data, indent=2)}

HISTORICAL CONTEXT FROM PROJECT DOCUMENTS:
{context}{team_section}{rejection_section}

Return exactly this JSON structure with three top-level analysis sections:
{{
  "talent_brief": {{
    "skills_required": [{{"name": "...", "criticality": "must|nice", "market_availability": "easy|moderate|hard"}}],
    "search_guidance": ["tip 1"],
    "historical_insights": ["insight [Source N]"],
    "pitfalls": ["mistake to avoid"],
    "estimated_time_to_fill_days": 30,
    "confidence": 0.75,
    "confidence_level": "HIGH|MEDIUM|LOW",
    "confidence_explanation": "...",
    "sources": ["source descriptions"],
    "reasoning": "3-5 sentences on skills team already has vs what hire must add",
    "key_arguments": [{{"point": "...", "evidence": "...", "impact": "positive|negative|neutral"}}]
  }},
  "historical_match": {{
    "similar_positions": [{{"project": "...", "role": "...", "outcome": "...", "time_to_fill": 45, "key_learnings": "... [Source N]"}}],
    "success_patterns": ["pattern [Source N]"],
    "failure_patterns": ["failure [Source N]"],
    "confidence": 0.6,
    "confidence_level": "HIGH|MEDIUM|LOW",
    "confidence_explanation": "...",
    "sources": ["source descriptions"],
    "reasoning": "3-5 sentences on historical patterns",
    "key_arguments": [{{"point": "...", "evidence": "...", "impact": "positive|negative|neutral"}}]
  }},
  "level_advisor": {{
    "recommended_level": "junior|mid|senior|lead",
    "reasoning": "explanation citing evidence [Source N]",
    "evidence": [{{"project": "...", "role": "...", "level": "...", "outcome": "..."}}],
    "risk_of_wrong_level": "what happens if wrong level hired",
    "confidence": 0.7,
    "confidence_level": "HIGH|MEDIUM|LOW",
    "confidence_explanation": "...",
    "sources": ["source descriptions"],
    "key_arguments": [{{"point": "...", "evidence": "...", "impact": "positive|negative|neutral"}}]
  }},
  "overall_confidence": 0.7,
  "reasoning": "1-2 sentence overall summary",
  "key_arguments": [{{"point": "...", "evidence": "...", "impact": "positive|negative|neutral"}}]
}}

Rules:
- talent_brief: team-covered skills → "nice", missing → "must"; search_guidance specific to team gaps
- talent_brief pitfalls: if HISTORICAL REJECTION PATTERNS are provided, include the most common rejection reasons as specific pitfalls to avoid (cite percentages if available)
- talent_brief historical_insights: if rejection patterns include AI accuracy data, include it as an insight
- historical_match failure_patterns: if HISTORICAL REJECTION PATTERNS are provided, translate rejection type counts into failure patterns (e.g. "40% of rejections were skill_gap — candidates lacked hands-on ETL experience")
- level_advisor: factor in existing team seniority; recommend level that balances composition
- key_arguments: 3-6 per section
- All lists must be arrays even if empty. Numbers must be integers/floats, not strings."""

        combined = await self._call_with_validation(prompt, "PI")

        a_data = combined.get("talent_brief") or {}
        b_data = combined.get("historical_match") or {}
        c_data = combined.get("level_advisor") or {}

        # Propagate overall_confidence to any section that lacks it
        overall_conf = combined.get("overall_confidence", 0.5)
        for section in (a_data, b_data, c_data):
            if not section.get("confidence"):
                section["confidence"] = overall_conf

        a_result = self._save_and_return("A", project_id, [jd_document_id], a_data)
        b_result = self._save_and_return("B", project_id, [jd_document_id], b_data)
        c_result = self._save_and_return("C", project_id, [jd_document_id], c_data)
        return a_result, b_result, c_result

    def _get_cached_mode_result(
        self, jd_document_id: int, mode: str
    ) -> dict[str, Any] | None:
        """Return a recent (< 1 hr) AnalysisResult for this mode + JD, or None."""
        from app.models.database import AnalysisResult, SessionLocal

        db = SessionLocal()
        try:
            cutoff = datetime.utcnow() - timedelta(hours=1)
            rows = (
                db.query(AnalysisResult)
                .filter(
                    AnalysisResult.analysis_mode == mode,
                    AnalysisResult.created_at >= cutoff,
                )
                .order_by(AnalysisResult.created_at.desc())
                .limit(20)
                .all()
            )
            for r in rows:
                if jd_document_id in (r.input_document_ids or []):
                    return {
                        "result_id": r.id,
                        "mode": mode,
                        "project_id": r.project_id,
                        "input_document_ids": r.input_document_ids,
                        **(r.result_data or {}),
                    }
            return None
        except Exception as exc:
            logger.warning("Cache check failed for mode %s: %s", mode, exc)
            return None
        finally:
            db.close()

    # ── Mode D — Candidate Scorer ─────────────────────────────────────────────

    async def candidate_score(
        self,
        resume_document_id: int,
        jd_document_id: int,
        interview_notes: str | None = None,
        client_feedback: str | None = None,
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
            query=self._build_retrieval_query(
                "candidate_score",
                jd_text=str(jd_data),
                candidate_name=candidate_name,
            ),
            project_id=str(project_id),
            doc_types=["resume", "interview", "report"],
            max_tokens=2000,
        )

        extra_context = ""
        data_sources = ["resume", "jd"]
        if interview_notes:
            extra_context += f"\n\nINTERVIEW NOTES (from our technical interview - weight heavily for technical assessment):\n{interview_notes}"
            data_sources.append("interview_notes")
        if client_feedback:
            extra_context += f"\n\nCLIENT FEEDBACK (from client-side interview - if negative, significantly lower overall score):\n{client_feedback}"
            data_sources.append("client_feedback")

        team_context = self._team_context(project_id)
        if team_context:
            data_sources.append("team_context")

        rejection_patterns = self._rejection_patterns(project_id)
        rejection_section = ""
        if rejection_patterns:
            data_sources.append("rejection_patterns")
            rejection_section = (
                f"\n\nHISTORICAL REJECTION PATTERNS FOR THIS PROJECT:\n{rejection_patterns}\n"
                "Use this to calibrate your assessment: if previous candidates were rejected for a specific skill gap "
                "and this candidate has the same gap, flag it prominently in the gaps list and lower the score accordingly."
            )

        prompt = f"""You are scoring a candidate against a job description using a STRICT STRUCTURED FORMULA.
You MUST follow the steps below IN ORDER and calculate the final score mathematically. Do NOT estimate or "feel" the score.

CANDIDATE RESUME:
{self._compress_resume(resume_data)}

JOB DESCRIPTION:
{json.dumps(jd_data, indent=2)}

HISTORICAL CONTEXT (similar hires, past outcomes):
{context}{extra_context}
{(f"{chr(10)}CURRENT PROJECT TEAM:{chr(10)}{team_context}" if team_context else "")}{rejection_section}

=== SCORING STEPS (follow exactly) ===

STEP 1 — ROLE ALIGNMENT GATE
Determine the candidate's ACTUAL role type from their experience (what they DID, not what they managed):
  - engineer/developer = writes code, builds systems, hands-on technical IC
  - manager = manages people, projects, timelines, stakeholders
  - analyst = analyzes data, writes reports, but doesn't build pipelines
  - designer, qa, devops, data_scientist, other

Determine the JD's required role type from the responsibilities section.

If these are DIFFERENT categories (e.g., candidate is "manager" but JD needs "engineer"):
  → role_alignment_score = 10
  → The MAXIMUM possible overall_score is 35, regardless of other scores
  → verdict MUST be "not_recommended"
  → You MUST state the mismatch in reasoning

If SAME category:
  → role_alignment_score = 100
  → No cap on overall_score

STEP 2 — HARD SKILLS MATCH (weight: 40%)
List every must-have skill from the JD.
For each skill, check the candidate's ACTUAL hands-on usage (not just listing it):
  - "hands_on" (1.0): candidate USED this skill as an IC — evidence: they built/wrote/developed/debugged with it
  - "exposure" (0.2): candidate LISTS the skill but only in management/oversight context (e.g., "managed teams using Python" ≠ "wrote Python code")
  - "none" (0.0): not mentioned at all

hard_skills_score = (sum of match values / number of must_have_skills) * 100

CRITICAL RULE: "Comfortable working in technical environments with exposure to X" or "managed a team that used X" = EXPOSURE (0.2), NOT hands-on (1.0).

STEP 3 — EXPERIENCE DEPTH (weight: 25%)
Count years of experience in the SAME ROLE TYPE as the JD requires:
  - If JD requires engineer: only count years as engineer/developer/IC contributor
  - Years as PM managing engineers = 0 engineering years
  - Years as analyst = 0 engineering years

Compare to JD requirement:
  - meets or exceeds = 100
  - 75-99% = 75
  - 50-74% = 50
  - 25-49% = 25
  - <25% or entirely wrong role type = 10

STEP 4 — DOMAIN & CONTEXT (weight: 15%)
  - Same industry as JD company (+40)
  - Similar company size/stage (+20)
  - Relevant domain-specific knowledge (+40)
  Max 100.

STEP 5 — SOFT SKILLS & CULTURE (weight: 10%)
  - Communication evidence (+35)
  - Collaboration evidence (+35)
  - Problem-solving examples (+30)
  Max 100.

STEP 6 — TEAM COMPLEMENTARITY (weight: 10%)
  - Fills genuine skill gap on current team (+50)
  - Brings new expertise not present (+30)
  - Seniority level fits team structure (+20)
  Max 100. If no team data provided, default to 50.

STEP 7 — CALCULATE FINAL SCORE
raw_score = (hard_skills_score × 0.40) + (experience_score × 0.25) + (domain_score × 0.15) + (soft_skills_score × 0.10) + (team_score × 0.10)

If role_alignment_score < 50:
    overall_score = min(raw_score, 35)
Else:
    overall_score = round(raw_score)

=== RESPOND WITH THIS EXACT JSON ===
{{
  "overall_score": <calculated integer 0-100>,
  "verdict": "strong_fit|moderate_fit|risky|not_recommended",
  "role_alignment": {{
    "candidate_role_type": "<detected type>",
    "jd_role_type": "<detected type>",
    "is_match": true,
    "role_alignment_score": <10 or 100>,
    "score_capped": false,
    "note": "<explanation if mismatch>"
  }},
  "skill_match": {{
    "score": <hard_skills_score integer>,
    "must_have_skills": [
      {{"skill": "Python", "match_level": "hands_on|exposure|none", "evidence": "specific quote or fact from resume"}}
    ],
    "matched": ["skills with hands_on or exposure"],
    "missing": ["skills with none"],
    "partial": ["skills with exposure only"]
  }},
  "experience_match": {{
    "score": <experience_score integer>,
    "relevant_years": <number of years in matching role type>,
    "required_years": <from JD>,
    "role_type_match": true,
    "notes": "explanation"
  }},
  "domain_match": {{
    "score": <domain_score integer>,
    "industry_match": true,
    "relevant_knowledge": ["list"]
  }},
  "soft_skills": {{
    "score": <soft_skills_score integer>,
    "communication": <0-35>,
    "collaboration": <0-35>,
    "problem_solving": <0-30>
  }},
  "team_compatibility": {{
    "score": <team_score integer>,
    "notes": "..."
  }},
  "team_complementarity": {{
    "score": <team_score integer>,
    "fills_gaps": [],
    "overlaps": [],
    "team_dynamics": "...",
    "recommendation": "..."
  }},
  "score_breakdown": {{
    "hard_skills_weighted": <score × 0.40>,
    "experience_weighted": <score × 0.25>,
    "domain_weighted": <score × 0.15>,
    "soft_skills_weighted": <score × 0.10>,
    "team_weighted": <score × 0.10>,
    "raw_total": <sum>,
    "role_cap_applied": false,
    "final_score": <overall_score>
  }},
  "strengths": ["concrete strength with evidence"],
  "gaps": ["gap — why it matters for THIS role"],
  "historical_comparison": {{
    "similar_hire": "...",
    "project": "...",
    "outcome": "... [Source N]"
  }},
  "confidence": 0.0,
  "confidence_level": "HIGH|MEDIUM|LOW",
  "confidence_explanation": "...",
  "sources": ["..."],
  "reasoning": "3-5 sentences. MUST mention role alignment result first. Then hard skills assessment. Then overall recommendation.",
  "key_arguments": [
    {{"point": "...", "evidence": "...", "impact": "positive|negative|neutral"}}
  ],
  "data_sources_used": {json.dumps(data_sources)}
}}

VERDICT RULES:
- If role_alignment_score < 50: verdict MUST be "not_recommended" regardless of score
- Otherwise: strong_fit (85+), moderate_fit (65-84), risky (45-64), not_recommended (<45)

ANTI-INFLATION RULES:
- "Managed a team using Python" ≠ "Knows Python". Match level = exposure (0.2), not hands_on (1.0).
- "Comfortable working in technical environments" = exposure to tech, not technical IC capability.
- PM experience does NOT count as engineering experience, even if the PM worked on technical projects.
- Domain expertise (same industry) cannot compensate for missing core technical skills.
- Soft skills score CANNOT push overall_score above the role alignment cap.

key_arguments: list 3-6 arguments with specific evidence from resume."""

        result = await self._call_with_validation(prompt, "D")
        return self._save_and_return(
            mode="D",
            project_id=project_id,
            input_doc_ids=[resume_document_id, jd_document_id],
            result=result,
        )

    # ── Mode E — JD Reality Check ─────────────────────────────────────────────

    async def jd_reality_check(self, jd_document_id: int) -> dict[str, Any]:
        """
        Audit a JD for accuracy and hiring necessity by comparing it with:
        - current team resumes (do we already have these skills?)
        - weekly reports (what does the team actually do vs what the JD claims?)
        """
        jd_data, project_id = self._load_extracted(jd_document_id)

        context = self._retrieval.get_context_for_analysis(
            query=self._build_retrieval_query(
                "jd_reality_check",
                jd_text=str(jd_data),
            ),
            project_id=str(project_id),
            doc_types=["report", "client_report", "resume", "interview"],
            max_tokens=2000,
        )
        team_context = self._team_context(project_id)
        reports_context = self._reports_context(project_id)

        prompt = f"""You are a senior hiring consultant auditing a job description for accuracy and necessity.

JOB DESCRIPTION UNDER REVIEW:
{json.dumps(jd_data, indent=2)}

CURRENT PROJECT TEAM (resumes and skills):
{team_context if team_context else "No team members on record."}

WHAT THE TEAM ACTUALLY DOES (from weekly reports):
{reports_context if reports_context else "No weekly reports available."}

ADDITIONAL DOCUMENT CONTEXT:
{context}

Perform a REALITY CHECK on this JD. Be HONEST and CHALLENGING. Respond with JSON:
{{
  "skills_vs_reality": {{
    "jd_requires": ["list all skills explicitly required by the JD"],
    "team_already_has": ["skills from the JD that existing team members already have — cite member roles"],
    "actually_needed": ["skills the team genuinely lacks based on reports and team composition"],
    "questionable_requirements": ["JD skills that don't match what the team actually does based on reports"]
  }},
  "workload_analysis": {{
    "jd_claims": "Summary of what the JD says this role will do",
    "report_reality": "What similar roles/team actually does based on weekly reports",
    "mismatches": ["specific discrepancies between JD claims and report reality"],
    "is_jd_accurate": true
  }},
  "necessity_check": {{
    "is_hire_justified": true,
    "reasoning": "Why or why not this hire is needed given the team and reports",
    "alternative_suggestions": ["Could an existing member cover this with training?", "Would a different role be more impactful?"],
    "priority": "critical|high|medium|low"
  }},
  "jd_improvement_suggestions": [
    "Specific suggestion to make the JD more accurate based on real project needs"
  ],
  "confidence": 0.6,
  "confidence_level": "HIGH|MEDIUM|LOW",
  "confidence_explanation": "How much team and report data was available to assess this",
  "sources": ["source descriptions"],
  "reasoning": "3-5 sentence overall assessment of this JD's accuracy and the hire's necessity. If the JD doesn't match reality, say so clearly. If the hire is redundant with existing team, say so.",
  "key_arguments": [
    {{"point": "one sentence argument", "evidence": "specific data from team or reports", "impact": "positive|negative|neutral"}}
  ]
}}

Rules:
- If no team data: skills_vs_reality.team_already_has = [], note this in confidence_explanation
- If no reports: workload_analysis.report_reality = "No weekly reports available to compare", is_jd_accurate = true (cannot verify)
- necessity_check.priority: critical = hire is clearly needed for project success; low = hire seems redundant or questionable
- key_arguments: list 3-6 arguments, each with point (one sentence), evidence (specific data), impact (positive/negative/neutral)
- All lists must be arrays even if empty."""

        result = await self._call_with_validation(prompt, "E")
        return self._save_and_return(
            mode="E",
            project_id=project_id,
            input_doc_ids=[jd_document_id],
            result=result,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    # ── Batch Candidate Scoring ───────────────────────────────────────────────

    async def batch_candidate_score(
        self,
        candidates_data: list[dict[str, Any]],
        jd_document_id: int,
    ) -> dict[int, dict[str, Any]]:
        """
        Score multiple candidates against a JD in batches of 8 (single LLM call per batch).
        candidates_data: list of {id, resume_data, resume_document_id, interview_notes?, client_feedback?}
        Returns {candidate_id: score_result_dict}.
        """
        if not candidates_data:
            return {}

        jd_data, project_id = self._load_extracted(jd_document_id)
        jd_title = jd_data.get("title", "this role")

        context = self._retrieval.get_context_for_analysis(
            query=self._build_retrieval_query(
                "candidate_score",
                jd_text=str(jd_data),
            ),
            project_id=str(project_id),
            doc_types=["resume", "interview", "report"],
            max_tokens=2000,
        )
        team_context = self._team_context(project_id)

        results: dict[int, dict[str, Any]] = {}
        batch_size = 8
        for i in range(0, len(candidates_data), batch_size):
            batch = candidates_data[i : i + batch_size]
            batch_results = await self._score_candidate_batch(
                batch, jd_data, project_id, jd_document_id, context, team_context
            )
            results.update(batch_results)
        return results

    async def _score_candidate_batch(
        self,
        batch: list[dict[str, Any]],
        jd_data: dict[str, Any],
        project_id: int,
        jd_document_id: int,
        context: str,
        team_context: str,
    ) -> dict[int, dict[str, Any]]:
        """Score up to 8 candidates in one LLM call."""
        jd_title = jd_data.get("title", "this role")
        n = len(batch)

        candidate_blocks = ""
        for c in batch:
            compressed = self._compress_resume(c.get("resume_data", {}))
            lines = [f"--- Candidate id={c['id']} ---", compressed]
            if c.get("interview_notes"):
                lines.append(f"Interview: {str(c['interview_notes'])[:400]}")
            if c.get("client_feedback"):
                lines.append(f"Client feedback: {str(c['client_feedback'])[:200]}")
            candidate_blocks += "\n".join(lines) + "\n\n"

        team_section = f"\nCURRENT PROJECT TEAM:\n{team_context}" if team_context else ""

        prompt = f"""You are scoring {n} candidates against a job description using a STRICT STRUCTURED FORMULA.

JOB DESCRIPTION:
{json.dumps(jd_data, indent=2)}

HISTORICAL CONTEXT (similar hires, past outcomes):
{context}{team_section}

CANDIDATES TO SCORE:
{candidate_blocks}

SCORING RULES (apply to EACH candidate independently):

1. ROLE ALIGNMENT: Determine if candidate's actual role type matches JD role type.
   - If mismatch (e.g., manager vs engineer): score capped at 35, verdict = not_recommended
   - "Managed teams using X" ≠ "hands-on with X"

2. HARD SKILLS (40% weight): For each must-have skill, assess hands_on (1.0) vs exposure (0.2) vs none (0.0)

3. EXPERIENCE (25% weight): Count only years in SAME role type as JD requires

4. DOMAIN (15% weight): Industry and domain knowledge match

5. SOFT SKILLS (10% weight): Communication, collaboration, problem-solving

6. TEAM FIT (10% weight): Fills gaps, complements existing team

Formula: raw = skills*0.4 + exp*0.25 + domain*0.15 + soft*0.1 + team*0.1
If role mismatch: final = min(raw, 35)

Return a JSON object with a "candidates" array. For each candidate, set "candidate_id" to the EXACT integer id number shown above:
{{
  "candidates": [
    {{
      "candidate_id": <exact id from above>,
      "overall_score": 0-100,
      "verdict": "strong_fit|moderate_fit|risky|not_recommended",
      "role_alignment": {{"candidate_role_type": "...", "jd_role_type": "...", "is_match": true, "role_alignment_score": 10 or 100, "score_capped": false, "note": "..."}},
      "skill_match": {{
        "score": 0-100,
        "must_have_skills": [{{"skill": "...", "match_level": "hands_on|exposure|none", "evidence": "..."}}],
        "matched": [...], "missing": [...], "partial": [...]
      }},
      "experience_match": {{"score": 0-100, "relevant_years": N, "required_years": N, "role_type_match": true, "notes": "..."}},
      "domain_match": {{"score": 0-100, "industry_match": true, "relevant_knowledge": [...]}},
      "soft_skills": {{"score": 0-100, "communication": 0-35, "collaboration": 0-35, "problem_solving": 0-30}},
      "team_compatibility": {{"score": 0-100, "notes": "..."}},
      "team_complementarity": {{
        "score": 0-100,
        "fills_gaps": [...], "overlaps": [...],
        "team_dynamics": "...", "recommendation": "..."
      }},
      "score_breakdown": {{
        "hard_skills_weighted": 0.0, "experience_weighted": 0.0, "domain_weighted": 0.0,
        "soft_skills_weighted": 0.0, "team_weighted": 0.0,
        "raw_total": 0.0, "role_cap_applied": false, "final_score": 0
      }},
      "strengths": ["strength 1"],
      "gaps": ["gap 1"],
      "historical_comparison": {{"similar_hire": "...", "project": "...", "outcome": "... [Source N]"}},
      "confidence": 0.0-1.0,
      "confidence_level": "HIGH|MEDIUM|LOW",
      "confidence_explanation": "...",
      "sources": ["..."],
      "reasoning": "2-3 sentences. Start with role alignment result.",
      "key_arguments": [{{"point": "...", "evidence": "...", "impact": "positive|negative|neutral"}}]
    }}
  ]
}}

Verdicts: strong_fit (85+), moderate_fit (65-84), risky (45-64), not_recommended (<45).
Evaluate each candidate independently. Include ALL {n} candidates.
key_arguments: 2-4 per candidate."""

        # ~600 tokens per candidate output + 500 buffer, cap at 8192
        batch_max_tokens = min(len(batch) * 600 + 500, 8192)

        validated: BatchScoringResult | None = None
        for attempt in range(2):
            response = await self._llm.generate(
                prompt=prompt,
                system_prompt=_SYSTEM_PROMPT,
                temperature=0.1,
                max_tokens=batch_max_tokens,
            )
            try:
                raw = parse_llm_json(response)
                if isinstance(raw, list):
                    raw = {"candidates": raw}
                validated = BatchScoringResult(**raw)
                break
            except (ValidationError, ValueError, json.JSONDecodeError) as exc:
                logger.warning("Batch scoring attempt %d failed: %s", attempt + 1, exc)
                if attempt == 0:
                    prompt += f"\n\nPREVIOUS ATTEMPT FAILED: {exc}\nFix and return valid JSON."
                else:
                    logger.error("Batch scoring failed after 2 attempts")
                    return {}

        if validated is None:
            return {}

        import re as _re

        output: dict[int, dict[str, Any]] = {}
        for idx, item in enumerate(validated.candidates):
            item_dict = item.model_dump()
            raw_cand_id = item_dict.pop("candidate_id")

            # Try direct numeric match first
            try:
                numeric_id = int(raw_cand_id)
                c_data = next((c for c in batch if c["id"] == numeric_id), None)
            except (ValueError, TypeError):
                c_data = None

            # Fallback: parse index from "CANDIDATE_1" style strings
            if c_data is None and isinstance(raw_cand_id, str):
                m = _re.search(r"(\d+)", str(raw_cand_id))
                if m:
                    candidate_idx = int(m.group(1)) - 1
                    if 0 <= candidate_idx < len(batch):
                        c_data = batch[candidate_idx]
                        logger.info(
                            "Resolved candidate_id '%s' by index → id=%d",
                            raw_cand_id, c_data["id"],
                        )

            # Last resort: positional match
            if c_data is None and idx < len(batch):
                c_data = batch[idx]
                logger.warning(
                    "Could not resolve candidate_id '%s', using positional match → id=%d",
                    raw_cand_id, c_data["id"],
                )

            if c_data is None:
                logger.error("Could not resolve candidate_id='%s', skipping", raw_cand_id)
                continue

            cand_id = c_data["id"]
            _ = cand_id  # used below
            saved = self._save_and_return(
                mode="D",
                project_id=project_id,
                input_doc_ids=[c_data["resume_document_id"], jd_document_id],
                result=item_dict,
            )
            output[c_data["id"]] = saved
        return output

    def _compress_resume(self, data: dict[str, Any]) -> str:
        """
        Compress resume structured_data to ~200-300 tokens for use in prompts.
        Handles both old field names (full_name/title/position/field/level) and
        new names (name/role/institution) so different LLM extractors are covered.
        """
        lines: list[str] = []

        name = data.get("full_name") or data.get("name", "Unknown")
        lines.append(f"Name: {name}")

        yoe = data.get("years_of_experience")
        if yoe is not None:
            lines.append(f"Total experience: {yoe} years")

        # Short professional summary — first 2 sentences only
        summary = data.get("summary") or data.get("professional_summary") or ""
        if summary:
            sentences = [s.strip() for s in summary.split(". ") if s.strip()]
            lines.append(f"Summary: {'. '.join(sentences[:2])}.")

        skills = data.get("skills") or data.get("technical_skills") or []
        if isinstance(skills, str):
            skills = [s.strip() for s in skills.split(",") if s.strip()]
        if skills:
            lines.append(f"Skills: {', '.join(str(s) for s in skills[:20])}")

        exp_list = data.get("work_experience") or data.get("experience") or []
        if isinstance(exp_list, list):
            import re as _re2

            def _extract_end_year(job: dict) -> int:
                duration = str(job.get("duration") or job.get("period") or "")
                years = _re2.findall(r"20\d{2}", duration)
                if years:
                    return max(int(y) for y in years)
                if any(w in duration.lower() for w in ("present", "current", "now", "ongoing")):
                    return 9999
                return 0

            sorted_exp = sorted(
                exp_list,
                key=lambda j: _extract_end_year(j) if isinstance(j, dict) else 0,
                reverse=True,
            )
            for job in sorted_exp[:3]:
                if isinstance(job, dict):
                    title = job.get("role") or job.get("title") or job.get("position", "")
                    company = job.get("company", "")
                    duration = job.get("duration") or job.get("period", "")
                    if title or company:
                        job_str = f"- {title} at {company}" if company else f"- {title}"
                        if duration:
                            job_str += f" ({duration})"
                        lines.append(job_str)

        edu_list = data.get("education") or []
        if isinstance(edu_list, list):
            for edu in edu_list[:2]:
                if isinstance(edu, dict):
                    deg = edu.get("degree") or edu.get("level", "")
                    school = edu.get("institution") or edu.get("school") or edu.get("field") or edu.get("specialization", "")
                    if deg:
                        lines.append(f"- {deg}{(', ' + school) if school else ''}")
        elif isinstance(edu_list, str) and edu_list:
            lines.append(f"Education: {edu_list[:120]}")

        loc = data.get("location")
        if loc:
            lines.append(f"Location: {loc}")

        lines.append("[NOTE: This is a compressed summary. Skills or experience not listed may still be present in the full resume.]")

        return "\n".join(lines)[:2000]

    # ── Private helpers ───────────────────────────────────────────────────────

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
                max_tokens=_MAX_TOKENS_MAP.get(mode, 2048),
            )
            try:
                raw = parse_llm_json(response)
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



def get_analysis_engine(llm: LLMProvider | None = None) -> AnalysisEngine:
    if llm is None:
        from app.services.llm.client import get_llm_client
        llm = get_llm_client()
    return AnalysisEngine(llm)
