"""
End-to-end tests for TalentLens API.

Flow:
  1.  Health check
  2.  Projects  — CRUD
  3.  Positions — CRUD + pipeline monitor
  4.  Documents — upload JD + resume, wait for processing
  5.  Team      — add member, update, skill-sync
  6.  Analysis  — sufficiency check + all 5 modes (A/B/C/D/E)
  7.  Candidates — add, score, update, timeline
  8.  Search    — hybrid search
  9.  Cleanup   — delete everything, verify 404s

All LLM / embedding / ChromaDB calls are mocked (see conftest.py).
"""
import io
import time

import pytest

# ── Shared state (populated as tests run in order) ────────────────────────────
_s: dict = {}


def _wait_for_job(client, job_id: int, timeout: int = 10) -> dict:
    """Poll GET /api/jobs/{id} until completed or failed."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/api/jobs/{job_id}")
        assert r.status_code == 200
        data = r.json()
        if data["status"] in ("completed", "failed"):
            return data
        time.sleep(0.3)
    pytest.fail(f"Job {job_id} did not complete within {timeout}s (last status: {data.get('status')})")


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Health
# ═══════════════════════════════════════════════════════════════════════════════

def test_01_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_02_root(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "TalentLens API"
    assert body["status"] == "running"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Projects
# ═══════════════════════════════════════════════════════════════════════════════

def test_03_create_project(client):
    r = client.post("/api/projects", json={
        "name": "E2E Test Project",
        "client_name": "Test Client Corp",
        "description": "Automated e2e test project",
        "status": "active",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "E2E Test Project"
    assert body["client_name"] == "Test Client Corp"
    assert body["status"] == "active"
    _s["project_id"] = body["id"]


def test_04_list_projects(client):
    r = client.get("/api/projects")
    assert r.status_code == 200
    body = r.json()
    items = body if isinstance(body, list) else body.get("items", body)
    ids = [p["id"] for p in items]
    assert _s["project_id"] in ids


def test_05_get_project(client):
    r = client.get(f"/api/projects/{_s['project_id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == _s["project_id"]
    assert body["name"] == "E2E Test Project"


def test_06_update_project(client):
    r = client.put(f"/api/projects/{_s['project_id']}", json={
        "name": "E2E Test Project",
        "client_name": "Test Client Corp",
        "description": "Updated description for e2e test",
        "status": "active",
    })
    assert r.status_code == 200, r.text
    assert r.json()["description"] == "Updated description for e2e test"


def test_07_project_404(client):
    r = client.get("/api/projects/999999")
    assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Positions
# ═══════════════════════════════════════════════════════════════════════════════

def test_08_create_position(client):
    r = client.post(
        f"/api/projects/{_s['project_id']}/positions",
        data={"title": "Senior Python Engineer", "level": "senior"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["title"] == "Senior Python Engineer"
    assert body["status"] == "open"
    _s["position_id"] = body["id"]


def test_09_list_positions(client):
    r = client.get(f"/api/projects/{_s['project_id']}/positions")
    assert r.status_code == 200
    ids = [p["id"] for p in r.json()["items"]]
    assert _s["position_id"] in ids


def test_10_get_position(client):
    r = client.get(f"/api/positions/{_s['position_id']}")
    assert r.status_code == 200
    assert r.json()["id"] == _s["position_id"]


def test_11_update_position(client):
    r = client.put(f"/api/positions/{_s['position_id']}", json={
        "title": "Senior Python Engineer (updated)",
        "level": "senior",
    })
    assert r.status_code == 200
    assert "updated" in r.json()["title"]


def test_12_pipeline_monitor(client):
    r = client.get("/api/pipeline")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    # Our open position should appear in pipeline (uses "id" field per PipelinePositionResponse)
    ids = [p["id"] for p in body]
    assert _s["position_id"] in ids


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Documents — upload JD + resume, wait for async processing
# ═══════════════════════════════════════════════════════════════════════════════

def test_13_upload_jd(client):
    jd_content = (
        "Senior Python Engineer\n\n"
        "We are looking for a Senior Python Engineer to join our team.\n\n"
        "REQUIREMENTS:\n"
        "- 5+ years Python experience\n"
        "- FastAPI framework experience\n"
        "- PostgreSQL database skills\n"
        "- Strong API design skills\n\n"
        "RESPONSIBILITIES:\n"
        "- Design and build REST APIs\n"
        "- Code reviews\n"
        "- Mentor junior developers\n"
    ).encode()
    r = client.post(
        f"/api/projects/{_s['project_id']}/documents",
        files={"file": ("senior_python_engineer_jd.txt", io.BytesIO(jd_content), "text/plain")},
        data={"doc_type_hint": "jd"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert "job_id" in body
    _s["jd_doc_id"] = body["id"]
    _s["jd_job_id"] = body["job_id"]

    # Wait for async processing
    job = _wait_for_job(client, _s["jd_job_id"])
    assert job["status"] == "completed", f"JD processing failed: {job}"


def test_14_upload_resume(client):
    resume_content = (
        "Alice Smith\n"
        "Senior Software Engineer\n"
        "alice@example.com | +1-555-0100\n\n"
        "SUMMARY\n"
        "Experienced Python developer with 4 years of hands-on backend development experience.\n\n"
        "EXPERIENCE\n"
        "TechCo - Senior Software Engineer (2020-2024)\n"
        "- Built and maintained Python REST APIs using FastAPI and PostgreSQL\n"
        "- Led API design for 3 major product features\n"
        "- Mentored 2 junior developers\n\n"
        "SKILLS\n"
        "Python, FastAPI, PostgreSQL, Docker, Git, SQL, REST API design\n\n"
        "EDUCATION\n"
        "MIT - BSc Computer Science (2018)\n"
    ).encode()
    r = client.post(
        f"/api/projects/{_s['project_id']}/documents",
        files={"file": ("alice_smith_resume.txt", io.BytesIO(resume_content), "text/plain")},
        data={"doc_type_hint": "resume"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    _s["resume_doc_id"] = body["id"]
    _s["resume_job_id"] = body["job_id"]

    job = _wait_for_job(client, _s["resume_job_id"])
    assert job["status"] == "completed", f"Resume processing failed: {job}"


def test_15_list_documents(client):
    r = client.get(f"/api/projects/{_s['project_id']}/documents")
    assert r.status_code == 200
    body = r.json()
    items = body if isinstance(body, list) else body.get("items", body)
    ids = [d["id"] for d in items]
    assert _s["jd_doc_id"] in ids
    assert _s["resume_doc_id"] in ids


def test_16_get_document_detail(client):
    r = client.get(f"/api/documents/{_s['jd_doc_id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == _s["jd_doc_id"]
    assert body["status"] == "processed"
    assert body["doc_type"] == "jd"
    # extracted_data should be populated
    assert body.get("extracted_data") is not None


def test_17_get_resume_detail(client):
    r = client.get(f"/api/documents/{_s['resume_doc_id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "processed"
    assert body["doc_type"] == "resume"
    assert body.get("extracted_data") is not None


def test_18_document_download(client):
    r = client.get(f"/api/documents/{_s['jd_doc_id']}/download")
    assert r.status_code == 200
    assert len(r.content) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Attach JD to position
# ═══════════════════════════════════════════════════════════════════════════════

def test_19_attach_jd_to_position(client):
    r = client.put(
        f"/api/positions/{_s['position_id']}/jd",
        data={"jd_document_id": str(_s["jd_doc_id"])},
    )
    assert r.status_code == 200, r.text
    assert r.json()["jd_document_id"] == _s["jd_doc_id"]


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Team
# ═══════════════════════════════════════════════════════════════════════════════

def test_20_add_team_member(client):
    r = client.post(
        f"/api/projects/{_s['project_id']}/team",
        data={"name": "Bob Williams", "role": "Backend Developer", "level": "mid"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "Bob Williams"
    assert body["level"] == "mid"
    _s["team_member_id"] = body["id"]


def test_21_list_team(client):
    r = client.get(f"/api/projects/{_s['project_id']}/team")
    assert r.status_code == 200
    body = r.json()
    member_ids = [m["id"] for m in body["items"]]
    assert _s["team_member_id"] in member_ids


def test_22_get_team_member(client):
    r = client.get(f"/api/team/{_s['team_member_id']}")
    assert r.status_code == 200
    assert r.json()["id"] == _s["team_member_id"]


def test_23_update_team_member(client):
    r = client.put(f"/api/team/{_s['team_member_id']}", json={
        "level": "senior",
        "notes": "Promoted to senior",
    })
    assert r.status_code == 200
    assert r.json()["level"] == "senior"


def test_24_upload_team_member_resume(client):
    resume_content = (
        "Bob Williams\n"
        "Backend Developer\n"
        "bob@example.com\n\n"
        "EXPERIENCE\n"
        "Current Co - Backend Developer (2021-present)\n"
        "- Python, Django, MySQL backend work\n\n"
        "SKILLS\n"
        "Python, Django, MySQL, REST APIs\n"
    ).encode()
    r = client.post(
        f"/api/team/{_s['team_member_id']}/resume",
        files={"file": ("bob_williams_resume.txt", io.BytesIO(resume_content), "text/plain")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    _s["team_resume_job_id"] = body.get("job_id")
    if _s["team_resume_job_id"]:
        job = _wait_for_job(client, _s["team_resume_job_id"])
        assert job["status"] == "completed"


def test_25_sync_team_member_skills(client):
    r = client.post(f"/api/team/{_s['team_member_id']}/sync-skills")
    assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Analysis
# ═══════════════════════════════════════════════════════════════════════════════

def test_26_sufficiency_check_mode_a(client):
    r = client.get(f"/api/analysis/sufficiency/{_s['project_id']}/A")
    assert r.status_code == 200
    body = r.json()
    assert body["can_run"] is True


def test_27_sufficiency_check_mode_d(client):
    r = client.get(f"/api/analysis/sufficiency/{_s['project_id']}/D")
    assert r.status_code == 200
    body = r.json()
    assert body["can_run"] is True


def test_28_mode_a_talent_brief(client):
    r = client.post("/api/analysis/talent-brief", json={
        "document_id": _s["jd_doc_id"],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert "skills_required" in body
    assert "search_guidance" in body
    assert len(body["skills_required"]) > 0
    _s["analysis_a_id"] = body.get("result_id")


def test_29_mode_b_historical_match(client):
    r = client.post("/api/analysis/historical-match", json={
        "document_id": _s["jd_doc_id"],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert "similar_positions" in body
    assert "success_patterns" in body


def test_30_mode_c_level_advisor(client):
    r = client.post("/api/analysis/level-advisor", json={
        "document_id": _s["jd_doc_id"],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert "recommended_level" in body
    assert body["recommended_level"] in ("junior", "mid", "senior", "lead")


def test_31_mode_d_candidate_score(client):
    r = client.post("/api/analysis/candidate-score", json={
        "resume_document_id": _s["resume_doc_id"],
        "jd_document_id": _s["jd_doc_id"],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    # Core score fields
    assert "overall_score" in body
    assert 0 <= body["overall_score"] <= 100
    assert body["verdict"] in ("strong_fit", "moderate_fit", "risky", "not_recommended")
    # New structured formula fields
    assert "role_alignment" in body
    assert body["role_alignment"]["role_alignment_score"] in (10, 100)
    assert "skill_match" in body
    assert "must_have_skills" in body["skill_match"]
    assert "score_breakdown" in body
    assert "hard_skills_weighted" in body["score_breakdown"]
    # Role match → no cap
    assert body["role_alignment"]["score_capped"] is False
    _s["analysis_d_id"] = body.get("result_id")


def test_32_mode_e_jd_reality_check(client):
    r = client.post("/api/analysis/jd-reality-check", json={
        "document_id": _s["jd_doc_id"],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert "skills_vs_reality" in body
    assert "necessity_check" in body
    assert "jd_improvement_suggestions" in body


def test_33_position_intelligence(client):
    r = client.post("/api/analysis/position-intelligence", json={
        "jd_document_id": _s["jd_doc_id"],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert "talent_brief" in body
    assert "historical_match" in body
    assert "level_advisor" in body


def test_34_analysis_results_list(client):
    r = client.get(f"/api/analysis/results/{_s['project_id']}")
    assert r.status_code == 200
    results = r.json()
    assert len(results) > 0
    modes = {result["analysis_mode"] for result in results}
    assert modes & {"A", "B", "C", "D", "E"}  # at least some modes present


def test_35_analysis_result_detail(client):
    if not _s.get("analysis_a_id"):
        pytest.skip("No analysis result ID captured")
    r = client.get(f"/api/analysis/results/detail/{_s['analysis_a_id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == _s["analysis_a_id"]
    assert body["analysis_mode"] == "A"


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Candidates
# ═══════════════════════════════════════════════════════════════════════════════

def test_36_add_candidate_with_resume(client):
    """Add candidate by linking the existing processed resume."""
    r = client.post(
        f"/api/positions/{_s['position_id']}/candidates",
        data={
            "name": "Alice Smith",
            "email": "alice@example.com",
            "resume_document_id": str(_s["resume_doc_id"]),
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "Alice Smith"
    assert body["email"] == "alice@example.com"
    _s["candidate_id"] = body["id"]


def test_37_list_candidates_for_position(client):
    r = client.get(f"/api/positions/{_s['position_id']}/candidates")
    assert r.status_code == 200
    ids = [c["id"] for c in r.json()["items"]]
    assert _s["candidate_id"] in ids


def test_38_get_candidate(client):
    r = client.get(f"/api/candidates/{_s['candidate_id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == _s["candidate_id"]
    assert body["name"] == "Alice Smith"


def test_39_update_candidate(client):
    r = client.put(f"/api/candidates/{_s['candidate_id']}", json={
        "status": "screening",
        "recruiter_notes": "Strong Python background, proceeding to technical screen",
        "years_of_experience": 4.0,
        "location": "San Francisco, CA",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "screening"
    assert body["recruiter_notes"] == "Strong Python background, proceeding to technical screen"


def test_40_score_candidate(client):
    r = client.post(f"/api/candidates/{_s['candidate_id']}/score")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ai_score"] is not None
    assert 0 <= body["ai_score"] <= 100
    assert body["ai_verdict"] in ("strong_fit", "moderate_fit", "risky", "not_recommended")


def test_41_score_all_candidates(client):
    r = client.post(f"/api/positions/{_s['position_id']}/score-all")
    assert r.status_code == 200, r.text
    results = r.json()
    assert isinstance(results, list)


def test_42_candidate_timeline(client):
    r = client.get(f"/api/candidates/{_s['candidate_id']}/timeline")
    assert r.status_code == 200
    events = r.json()
    assert isinstance(events, list)
    # Should have at least a status_change event from test_39
    event_types = [e["event_type"] for e in events]
    assert "status_change" in event_types or "scored" in event_types


def test_43_project_candidates(client):
    r = client.get(f"/api/projects/{_s['project_id']}/candidates")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    ids = [c["id"] for c in body["items"]]
    assert _s["candidate_id"] in ids


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Search
# ═══════════════════════════════════════════════════════════════════════════════

def test_44_search(client):
    r = client.post("/api/search", json={
        "query": "Python FastAPI engineer",
        "project_id": str(_s["project_id"]),
        "top_k": 5,
    })
    # Vector store is mocked → returns empty results, but endpoint should not crash
    assert r.status_code == 200, r.text
    body = r.json()
    assert "results" in body


# ═══════════════════════════════════════════════════════════════════════════════
# 10. Cleanup — delete in reverse dependency order
# ═══════════════════════════════════════════════════════════════════════════════

def test_45_delete_candidate(client):
    r = client.delete(f"/api/candidates/{_s['candidate_id']}")
    assert r.status_code == 204, r.text

    r = client.get(f"/api/candidates/{_s['candidate_id']}")
    assert r.status_code == 404


def test_46_delete_team_member(client):
    r = client.delete(f"/api/team/{_s['team_member_id']}")
    assert r.status_code in (200, 204), r.text


def test_47_delete_position(client):
    r = client.delete(f"/api/positions/{_s['position_id']}")
    assert r.status_code == 204, r.text

    r = client.get(f"/api/positions/{_s['position_id']}")
    assert r.status_code == 404


def test_48_delete_document(client):
    r = client.delete(f"/api/documents/{_s['jd_doc_id']}")
    assert r.status_code == 204, r.text

    r = client.get(f"/api/documents/{_s['jd_doc_id']}")
    assert r.status_code == 404


def test_49_delete_project(client):
    # Hard-delete team member from DB first (soft-delete via API keeps row,
    # which causes NOT NULL violation when project cascade-deletes).
    from app.models.database import SessionLocal, TeamMember
    db = SessionLocal()
    try:
        db.query(TeamMember).filter(
            TeamMember.project_id == _s["project_id"]
        ).delete()
        db.commit()
    finally:
        db.close()

    r = client.delete(f"/api/projects/{_s['project_id']}")
    assert r.status_code == 204, r.text

    r = client.get(f"/api/projects/{_s['project_id']}")
    assert r.status_code == 404


def test_50_project_gone_from_list(client):
    r = client.get("/api/projects")
    assert r.status_code == 200
    body = r.json()
    items = body if isinstance(body, list) else body.get("items", body)
    ids = [p["id"] for p in items]
    assert _s["project_id"] not in ids
