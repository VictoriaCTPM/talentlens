"""
Shared fixtures for TalentLens e2e tests.

Patches:
  - LLM → MockLLM (returns deterministic JSON, no network calls)
  - EmbeddingService → returns 384-dim zero vectors
  - VectorStore → no-op (in-memory ChromaDB stub)

DB: separate SQLite file (data/test_e2e.db), wiped before each session.
"""
import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ── Path setup ────────────────────────────────────────────────────────────────
_BACKEND = Path(__file__).parent.parent
sys.path.insert(0, str(_BACKEND))
os.chdir(_BACKEND)

TEST_DB_PATH = _BACKEND / "data" / "test_e2e.db"
TEST_DB_URL = f"sqlite:///{TEST_DB_PATH}"

# ── Mock responses ─────────────────────────────────────────────────────────────

_JD_EXTRACT = {
    "doc_type": "jd",
    "structured_data": {
        "title": "Senior Python Engineer",
        "company": "TestCorp",
        "level": "senior",
        "required_skills": ["Python", "FastAPI", "PostgreSQL"],
        "nice_to_have_skills": ["Docker", "Kubernetes"],
        "responsibilities": ["Design REST APIs", "Code review"],
        "requirements": ["5+ years Python", "Strong API design skills"],
    },
}

_RESUME_EXTRACT = {
    "doc_type": "resume",
    "structured_data": {
        "name": "Alice Smith",
        "email": "alice@example.com",
        "phone": "+1-555-0100",
        "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
        "experience": [
            {
                "company": "TechCo",
                "role": "Senior Software Engineer",
                "duration": "4 years",
                "description": "Built and maintained Python REST APIs using FastAPI and PostgreSQL",
            }
        ],
        "education": [{"institution": "MIT", "degree": "BSc Computer Science", "year": "2018"}],
        "summary": "Experienced Python developer with 5+ years of backend development",
    },
}

_TALENT_BRIEF = {
    "skills_required": [
        {"name": "Python", "criticality": "must", "market_availability": "moderate"},
        {"name": "FastAPI", "criticality": "must", "market_availability": "moderate"},
    ],
    "search_guidance": ["Target Python developers with 5+ years backend experience"],
    "historical_insights": ["Similar roles filled within 30 days [Source 1]"],
    "pitfalls": ["Avoid candidates with only frontend experience"],
    "estimated_time_to_fill_days": 30,
    "confidence": 0.85,
    "confidence_level": "HIGH",
    "confidence_explanation": "Sufficient historical data from project documents",
    "sources": ["JD: Senior Python Engineer"],
    "reasoning": "Strong Python developer market; FastAPI experience is key differentiator",
    "key_arguments": [
        {"point": "Python is in high demand", "evidence": "JD requirements [Source 1]", "impact": "positive"}
    ],
}

_HISTORICAL_MATCH = {
    "similar_positions": [
        {
            "project": "Alpha Project",
            "role": "Python Developer",
            "outcome": "Hired successfully, shipped in 2 months [Source 1]",
            "time_to_fill": 28,
            "key_learnings": "Strong Python skills more important than domain knowledge",
        }
    ],
    "success_patterns": ["Python-first candidates performed well [Source 1]"],
    "failure_patterns": ["Candidates without FastAPI experience struggled [Source 1]"],
    "confidence": 0.75,
    "confidence_level": "MEDIUM",
    "confidence_explanation": "Limited historical data",
    "sources": ["JD: Senior Python Engineer"],
    "reasoning": "Historical patterns suggest Python-first approach works best",
    "key_arguments": [
        {"point": "Python expertise predicts success", "evidence": "Source 1", "impact": "positive"}
    ],
}

_LEVEL_ADVISOR = {
    "recommended_level": "senior",
    "reasoning": "Based on project complexity, senior level is appropriate [Source 1]",
    "evidence": [
        {"project": "Alpha Project", "role": "Python Developer", "level": "senior", "outcome": "Successful"}
    ],
    "risk_of_wrong_level": "Junior would slow delivery; lead may be over-qualified",
    "confidence": 0.8,
    "confidence_level": "HIGH",
    "confidence_explanation": "Clear evidence from past projects",
    "sources": ["JD: Senior Python Engineer"],
    "key_arguments": [
        {"point": "Senior level matches project needs", "evidence": "Source 1", "impact": "positive"}
    ],
}

_POSITION_INTELLIGENCE = {
    "talent_brief": _TALENT_BRIEF,
    "historical_match": _HISTORICAL_MATCH,
    "level_advisor": _LEVEL_ADVISOR,
    "overall_confidence": 0.8,
    "reasoning": "Strong historical evidence supports this hire",
    "key_arguments": [
        {"point": "Well-matched to past successful hires", "evidence": "Source 1", "impact": "positive"}
    ],
}

_CANDIDATE_SCORE = {
    "overall_score": 82,
    "verdict": "moderate_fit",
    "role_alignment": {
        "candidate_role_type": "engineer",
        "jd_role_type": "engineer",
        "is_match": True,
        "role_alignment_score": 100,
        "score_capped": False,
        "note": "",
    },
    "skill_match": {
        "score": 88,
        "must_have_skills": [
            {"skill": "Python", "match_level": "hands_on", "evidence": "4 years Python at TechCo"},
            {"skill": "FastAPI", "match_level": "hands_on", "evidence": "Built REST APIs with FastAPI"},
            {"skill": "PostgreSQL", "match_level": "hands_on", "evidence": "Used PostgreSQL in production"},
        ],
        "matched": ["Python", "FastAPI", "PostgreSQL"],
        "missing": [],
        "partial": [],
    },
    "experience_match": {
        "score": 90,
        "relevant_years": 4,
        "required_years": 5,
        "role_type_match": True,
        "notes": "4 years as Senior Engineer — slightly below 5yr requirement but strong quality",
    },
    "domain_match": {
        "score": 70,
        "industry_match": True,
        "relevant_knowledge": ["SaaS product development", "API design"],
    },
    "soft_skills": {
        "score": 75,
        "communication": 30,
        "collaboration": 30,
        "problem_solving": 15,
    },
    "team_compatibility": {"score": 80, "notes": "Good fit with current team structure"},
    "team_complementarity": {
        "score": 80,
        "fills_gaps": ["Python expertise", "FastAPI experience"],
        "overlaps": [],
        "team_dynamics": "Would complement existing team well",
        "recommendation": "Strong recommendation — fills key technical gaps",
    },
    "score_breakdown": {
        "hard_skills_weighted": 35.2,
        "experience_weighted": 22.5,
        "domain_weighted": 10.5,
        "soft_skills_weighted": 7.5,
        "team_weighted": 8.0,
        "raw_total": 83.7,
        "role_cap_applied": False,
        "final_score": 82,
    },
    "strengths": ["Strong Python/FastAPI hands-on experience", "Relevant industry background"],
    "gaps": ["1 year below required experience — minor risk"],
    "historical_comparison": {
        "similar_hire": "John Doe — Python Developer",
        "project": "Alpha Project",
        "outcome": "Highly successful, shipped on time [Source 1]",
    },
    "confidence": 0.85,
    "confidence_level": "HIGH",
    "confidence_explanation": "Clear resume data and historical comparison available",
    "sources": ["Resume: Alice Smith", "JD: Senior Python Engineer"],
    "reasoning": "Role alignment is confirmed (engineer vs engineer). Hard skills are strong with hands-on Python, FastAPI, and PostgreSQL. Overall strong fit with minor experience gap.",
    "key_arguments": [
        {"point": "Hands-on Python experience confirmed", "evidence": "4 years at TechCo", "impact": "positive"},
        {"point": "Slight experience gap", "evidence": "4 vs 5 required years", "impact": "negative"},
    ],
    "data_sources_used": ["resume", "jd"],
}

_JD_REALITY_CHECK = {
    "skills_vs_reality": {
        "jd_requires": ["Python", "FastAPI", "PostgreSQL"],
        "team_already_has": ["Python"],
        "actually_needed": ["FastAPI", "PostgreSQL"],
        "questionable_requirements": [],
    },
    "workload_analysis": {
        "jd_claims": "Build and maintain REST APIs",
        "report_reality": "Team is building REST APIs and needs additional capacity",
        "mismatches": [],
        "is_jd_accurate": True,
    },
    "necessity_check": {
        "is_hire_justified": True,
        "reasoning": "Team lacks FastAPI expertise and needs backend capacity",
        "alternative_suggestions": ["Could train existing junior dev, but timeline too tight"],
        "priority": "high",
    },
    "jd_improvement_suggestions": ["Add specific mention of async Python experience"],
    "confidence": 0.7,
    "confidence_level": "MEDIUM",
    "confidence_explanation": "Limited report data but clear team gap identified",
    "sources": ["JD: Senior Python Engineer", "Team composition"],
    "reasoning": "The JD accurately reflects project needs. Team has Python but lacks FastAPI depth. Hire is justified.",
    "key_arguments": [
        {"point": "Team lacks FastAPI expertise", "evidence": "Team skills audit", "impact": "positive"}
    ],
}


class MockLLM:
    """Deterministic mock LLM for testing."""

    provider_name = "mock"
    model_name = "mock-model"

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        # Extraction-only prompt (doc_type_hint was provided — prompt starts with
        # "Extract structured data from this {doc_type} document.")
        if prompt.startswith("Extract structured data from this"):
            if "resume document" in prompt:
                return json.dumps({"extracted": _RESUME_EXTRACT["structured_data"]})
            # jd / job_request
            return json.dumps({"extracted": _JD_EXTRACT["structured_data"]})

        # Full classify+extract prompt (no hint provided)
        if "DOCUMENT TEXT" in prompt and "doc_type" in prompt:
            # Check FILENAME line to determine type
            for line in prompt.splitlines():
                if line.startswith("FILENAME:"):
                    fname = line.lower()
                    if any(kw in fname for kw in ["resume", "cv", "alice", "bob"]):
                        return json.dumps(_RESUME_EXTRACT)
                    break
            return json.dumps(_JD_EXTRACT)

        # Position Intelligence (A+B+C merged)
        if '"talent_brief"' in prompt and '"historical_match"' in prompt:
            return json.dumps(_POSITION_INTELLIGENCE)

        # Mode D — candidate scoring (structured formula prompt)
        if "SCORING STEPS" in prompt or "role_alignment_score" in prompt:
            return json.dumps(_CANDIDATE_SCORE)

        # Mode E — JD reality check
        if "REALITY CHECK" in prompt or "jd_improvement_suggestions" in prompt:
            return json.dumps(_JD_REALITY_CHECK)

        # Mode A standalone
        if "talent_brief" in prompt and "search_guidance" in prompt:
            return json.dumps(_TALENT_BRIEF)

        # Mode B standalone
        if "success_patterns" in prompt and "failure_patterns" in prompt:
            return json.dumps(_HISTORICAL_MATCH)

        # Mode C standalone
        if "recommended_level" in prompt and "risk_of_wrong_level" in prompt:
            return json.dumps(_LEVEL_ADVISOR)

        # Batch scoring
        if '"candidates"' in prompt and "candidate_id" in prompt:
            candidates_section = prompt.split("CANDIDATES TO SCORE")[1] if "CANDIDATES TO SCORE" in prompt else ""
            import re
            ids = re.findall(r"id=(\d+)", candidates_section)
            results = []
            for cid in ids:
                item = dict(_CANDIDATE_SCORE)
                item["candidate_id"] = int(cid)
                results.append(item)
            return json.dumps({"candidates": results})

        # Fallback
        return json.dumps({"error": "unknown prompt type", "raw": prompt[:100]})


class MockEmbeddingService:
    def embed_text(self, text: str) -> list[float]:
        return [0.0] * 384

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 384 for _ in texts]


class MockVectorStore:
    def add_chunks(self, *args, **kwargs):
        pass

    def search(self, *args, **kwargs):
        return []

    def get_all(self, *args, **kwargs):
        return []

    def delete_by_document(self, *args, **kwargs):
        pass

    def delete_by_project(self, *args, **kwargs):
        pass

    def hybrid_search(self, *args, **kwargs):
        return []


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def patch_services():
    """Patch LLM, embeddings, and vector store for the entire test session."""
    mock_llm = MockLLM()
    mock_emb = MockEmbeddingService()
    mock_vs = MockVectorStore()

    with (
        pytest.MonkeyPatch.context() as mp,
    ):
        # LLM client
        import app.services.llm.client as llm_client_mod
        mp.setattr(llm_client_mod, "get_llm_client", lambda *a, **kw: mock_llm)

        # Embeddings
        import app.services.embeddings as emb_mod
        mp.setattr(emb_mod, "get_embedding_service", lambda: mock_emb)

        # Vector store
        import app.services.vector_store as vs_mod
        mp.setattr(vs_mod, "get_vector_store", lambda: mock_vs)

        # Also patch inside job_queue (it imports locally)
        import app.services.job_queue as jq_mod
        mp.setattr(jq_mod, "get_embedding_service", mock_emb.__class__, raising=False)

        yield


@pytest.fixture(scope="session")
def client(patch_services):
    """Session-scoped TestClient with a dedicated test SQLite DB."""
    from app.models.database import Base, get_db

    # ── Use a separate test DB ────────────────────────────────────────────────
    TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    from app.main import app
    app.dependency_overrides[get_db] = override_get_db

    # Override the SessionLocal used by job_queue and analysis (they call it directly)
    import app.models.database as db_mod
    original_session_local = db_mod.SessionLocal
    db_mod.SessionLocal = TestingSession

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.clear()
    db_mod.SessionLocal = original_session_local

    # Cleanup test DB
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
