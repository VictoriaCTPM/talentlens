"""
Seed script: clears all data and inserts 3 fully-equipped test projects.
Run from backend/ with the venv active:
    python seed.py
"""
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ── Ensure project root is in path ───────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
os.chdir(Path(__file__).parent)

from app.config.settings import settings
from app.models.database import (
    AnalysisResult, Base, Candidate, CandidateEvent,
    Document, ExtractedData, Position, ProcessingJob,
    Project, SessionLocal, TeamMember, engine,
)

# ─────────────────────────────────────────────────────────────────────────────
# 0. Create tables (idempotent)
# ─────────────────────────────────────────────────────────────────────────────
Base.metadata.create_all(bind=engine)

# ─────────────────────────────────────────────────────────────────────────────
# 1. Wipe ChromaDB
# ─────────────────────────────────────────────────────────────────────────────
try:
    from app.services.vector_store import get_vector_store
    vs = get_vector_store()
    try:
        vs._client.delete_collection(vs._collection.name)
        print("ChromaDB collection wiped")
    except Exception:
        pass
except Exception as e:
    print(f"ChromaDB wipe skipped: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# 2. Wipe DB (FK-safe order)
# ─────────────────────────────────────────────────────────────────────────────
db = SessionLocal()
try:
    for Model in [
        CandidateEvent, Candidate, AnalysisResult, ExtractedData,
        ProcessingJob, Position, Document, TeamMember, Project,
    ]:
        db.query(Model).delete()
    db.commit()
    print("DB wiped")
finally:
    db.close()

# ─────────────────────────────────────────────────────────────────────────────
# 3. Wipe upload dir
# ─────────────────────────────────────────────────────────────────────────────
upload_root = Path(settings.UPLOAD_DIR)
if upload_root.exists():
    shutil.rmtree(upload_root)
upload_root.mkdir(parents=True, exist_ok=True)
print("Upload dir cleaned")

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
_now = datetime.utcnow

def _days_ago(n: int) -> datetime:
    return _now() - timedelta(days=n)


def _make_file(project_id: int, name: str, content: str) -> tuple[str, str, str]:
    """Write a fake text file, return (filename, file_path, content_hash)."""
    d = upload_root / str(project_id)
    d.mkdir(parents=True, exist_ok=True)
    fname = f"{hashlib.md5(name.encode()).hexdigest()}.txt"
    path = d / fname
    path.write_text(content, encoding="utf-8")
    chash = hashlib.sha256(content.encode()).hexdigest()
    return fname, str(path), chash


def _doc(db, project_id, original_name, content, doc_type, extracted_data):
    fname, fpath, chash = _make_file(project_id, original_name, content)
    doc = Document(
        project_id=project_id,
        filename=fname,
        original_filename=original_name,
        file_path=fpath,
        file_type="txt",
        doc_type=doc_type,
        file_size=len(content.encode()),
        status="processed",
        content_hash=chash,
        processed_at=_now(),
    )
    db.add(doc)
    db.flush()
    ed = ExtractedData(
        document_id=doc.id,
        doc_type=doc_type,
        structured_data=extracted_data,
        extraction_model="llama-3.3-70b-versatile",
        extraction_prompt_version="1.0",
        schema_version="1.0",
    )
    db.add(ed)
    return doc


def _analysis(db, project_id, mode, input_ids, result_data, confidence=0.8):
    ar = AnalysisResult(
        project_id=project_id,
        analysis_mode=mode,
        input_document_ids=input_ids,
        result_data=result_data,
        confidence_score=confidence,
        source_citations=result_data.get("sources", []),
        model_used="llama-3.3-70b-versatile",
        prompt_version="1.0",
    )
    db.add(ar)
    db.flush()
    return ar


def _candidate(db, position_id, name, email, phone, location, years_exp,
               status, score, verdict, analysis_id, resume_doc_id,
               recruiter_notes="", interview_notes="", client_feedback="",
               rejection_reason="", tags=None,
               candidate_rate=None, candidate_rate_period="monthly",
               availability="2 weeks notice"):
    c = Candidate(
        position_id=position_id,
        name=name, email=email, phone=phone, location=location,
        years_of_experience=years_exp, status=status,
        ai_score=score, ai_verdict=verdict, ai_analysis_id=analysis_id,
        resume_document_id=resume_doc_id,
        recruiter_notes=recruiter_notes, interview_notes=interview_notes,
        client_feedback=client_feedback, rejection_reason=rejection_reason,
        tags=tags or [],
        candidate_rate=candidate_rate, candidate_rate_period=candidate_rate_period,
        candidate_rate_currency="USD", availability=availability,
    )
    db.add(c)
    db.flush()
    db.add(CandidateEvent(candidate_id=c.id, event_type="created",
                          event_data={"name": name, "position_id": position_id},
                          created_at=_days_ago(10)))
    if status != "new":
        db.add(CandidateEvent(candidate_id=c.id, event_type="status_change",
                              event_data={"from": "new", "to": status},
                              created_at=_days_ago(7)))
    if score is not None:
        db.add(CandidateEvent(candidate_id=c.id, event_type="scored",
                              event_data={"score": score, "verdict": verdict},
                              created_at=_days_ago(5)))
    return c


# ═════════════════════════════════════════════════════════════════════════════
# PROJECT 1: Novex Digital — Mobile Payment Platform
# ═════════════════════════════════════════════════════════════════════════════
db = SessionLocal()
try:
    # ── Project ──────────────────────────────────────────────────────────────
    p1 = Project(
        name="Novex Digital — Mobile Payments",
        client_name="Novex Digital GmbH",
        description="Building a high-throughput mobile payment gateway. Team of 3 backend/devops, looking for a senior backend engineer and QA automation.",
        status="active",
    )
    db.add(p1)
    db.flush()
    pid = p1.id

    # ── Team resumes ─────────────────────────────────────────────────────────
    tm1_res = _doc(db, pid, "anna_kowalski_resume.txt",
        "Anna Kowalski — Lead Backend Engineer\nExperience: 8 years\nSkills: Python, FastAPI, PostgreSQL, Redis, Docker, Kubernetes, Celery, AWS\nCurrent role: Lead Backend at Novex. Designed the payments core service.\nEducation: Warsaw University of Technology, CS",
        "resume",
        {"full_name": "Anna Kowalski", "email": "anna@novex.io", "years_of_experience": 8,
         "skills": ["Python", "FastAPI", "PostgreSQL", "Redis", "Docker", "Kubernetes", "Celery", "AWS"],
         "current_role": "Lead Backend Engineer", "summary": "Leads backend architecture for payment systems."})

    tm2_res = _doc(db, pid, "marek_nowak_resume.txt",
        "Marek Nowak — Mid Frontend Engineer\nExperience: 4 years\nSkills: React, TypeScript, Next.js, GraphQL, CSS\nBuilds customer-facing payment UI.",
        "resume",
        {"full_name": "Marek Nowak", "email": "marek@novex.io", "years_of_experience": 4,
         "skills": ["React", "TypeScript", "Next.js", "GraphQL", "CSS"],
         "summary": "Frontend specialist for payment UIs."})

    tm3_res = _doc(db, pid, "piotr_wisniewski_resume.txt",
        "Piotr Wiśniewski — Senior DevOps\nExperience: 6 years\nSkills: Kubernetes, Terraform, AWS, CI/CD, GitLab, Prometheus, Grafana\nManages cloud infra, deploys to AWS EKS.",
        "resume",
        {"full_name": "Piotr Wiśniewski", "email": "piotr@novex.io", "years_of_experience": 6,
         "skills": ["Kubernetes", "Terraform", "AWS", "CI/CD", "GitLab", "Prometheus", "Grafana"],
         "summary": "Manages AWS Kubernetes infrastructure for payment platform."})

    # ── Team members ─────────────────────────────────────────────────────────
    tm1 = TeamMember(project_id=pid, name="Anna Kowalski", role="Lead Backend Engineer",
                     level="lead",
                     skills=["Python", "FastAPI", "PostgreSQL", "Redis", "Docker", "Kubernetes", "AWS"],
                     resume_document_id=tm1_res.id, status="active",
                     start_date=_days_ago(365))
    tm2 = TeamMember(project_id=pid, name="Marek Nowak", role="Mid Frontend Engineer",
                     level="mid",
                     skills=["React", "TypeScript", "Next.js", "GraphQL"],
                     resume_document_id=tm2_res.id, status="active",
                     start_date=_days_ago(200))
    tm3 = TeamMember(project_id=pid, name="Piotr Wiśniewski", role="Senior DevOps Engineer",
                     level="senior",
                     skills=["Kubernetes", "Terraform", "AWS", "CI/CD", "Prometheus"],
                     resume_document_id=tm3_res.id, status="active",
                     start_date=_days_ago(300))
    db.add_all([tm1, tm2, tm3])
    db.flush()

    # Weekly reports linked to team members
    rep1 = _doc(db, pid, "anna_weekly_report_w10.txt",
        "Weekly Report — Anna Kowalski — Week 10\nWork done: Implemented idempotency layer for payment processing, reviewed PR for Redis caching, fixed race condition in transaction rollback.\nChallenges: Load testing revealed bottlenecks at 5000 TPS.\nNext week: Optimize DB connection pool, add circuit breaker pattern.",
        "report",
        {"developer_name": "Anna Kowalski", "week": "W10", "tasks_completed": ["idempotency layer", "Redis caching review", "race condition fix"]})
    rep1.team_member_id = tm1.id

    rep2 = _doc(db, pid, "piotr_weekly_report_w10.txt",
        "Weekly Report — Piotr Wiśniewski — Week 10\nWork done: Upgraded EKS cluster to 1.29, set up Grafana dashboards for payment latency, configured autoscaling for peak loads.\nChallenges: EKS node group upgrade caused 2-minute downtime.\nNext week: Blue-green deployment for zero-downtime upgrades.",
        "report",
        {"developer_name": "Piotr Wiśniewski", "week": "W10", "tasks_completed": ["EKS upgrade", "Grafana dashboards", "autoscaling config"]})
    rep2.team_member_id = tm3.id

    # ── JD: Senior Backend Engineer ───────────────────────────────────────────
    jd1 = _doc(db, pid, "senior_backend_jd.txt",
        "Job Description: Senior Backend Engineer\nCompany: Novex Digital GmbH\nRole: Senior Backend Engineer — Payment Systems\nRequired Skills: Python, FastAPI or Django, PostgreSQL, Redis, Docker, REST API design, high-throughput systems\nNice to have: Kafka, gRPC, AWS Lambda\nExperience: 5+ years backend, 2+ years in fintech or payments\nResponsibilities: Design and implement payment processing microservices, ensure PCI-DSS compliance, 99.99% uptime, mentor junior developers.\nSalary: $8,000-12,000/month",
        "jd",
        {"title": "Senior Backend Engineer", "required_skills": ["Python", "FastAPI", "PostgreSQL", "Redis", "Docker", "REST API"],
         "preferred_skills": ["Kafka", "gRPC", "AWS Lambda"],
         "requirements": ["5+ years backend experience", "Fintech/payments domain", "High-throughput systems design"],
         "seniority_level": "senior", "location": "Remote (EU)", "employment_type": "B2B Contract",
         "salary_range": "$8,000-12,000/month"})

    # ── JD: QA Automation (filled position — closed) ──────────────────────────
    jd2 = _doc(db, pid, "qa_automation_jd.txt",
        "Job Description: QA Automation Engineer\nRequired: Selenium, Python, Pytest, CI/CD, API testing\nExperience: 3+ years QA automation",
        "jd",
        {"title": "QA Automation Engineer", "required_skills": ["Selenium", "Python", "Pytest", "API testing"],
         "seniority_level": "mid", "employment_type": "B2B"})

    # ── Positions ─────────────────────────────────────────────────────────────
    pos1 = Position(project_id=pid, title="Senior Backend Engineer", level="senior",
                    status="open", jd_document_id=jd1.id,
                    client_rate=14000.0, client_rate_currency="USD", client_rate_period="monthly",
                    created_at=_days_ago(15))
    pos2 = Position(project_id=pid, title="QA Automation Engineer", level="mid",
                    status="filled", jd_document_id=jd2.id,
                    created_at=_days_ago(40), closed_at=_days_ago(5))
    db.add_all([pos1, pos2])
    db.flush()

    # ── Analysis: Mode A (Talent Brief for pos1) ──────────────────────────────
    ar_A = _analysis(db, pid, "A", [jd1.id], {
        "skills_required": [
            {"name": "Python", "criticality": "nice", "notes": "Anna already covers Python — candidate must add something beyond basics"},
            {"name": "FastAPI", "criticality": "nice", "notes": "Anna uses FastAPI daily — must-have for collaboration"},
            {"name": "PostgreSQL", "criticality": "nice", "notes": "Covered by Anna"},
            {"name": "Redis", "criticality": "nice", "notes": "Covered by Anna"},
            {"name": "Kafka", "criticality": "must", "notes": "Nobody on team has Kafka — key gap for async processing"},
            {"name": "gRPC", "criticality": "must", "notes": "gRPC not represented on team"},
            {"name": "Fintech domain", "criticality": "must", "notes": "PCI-DSS and payment compliance experience missing"},
        ],
        "search_guidance": [
            "Team already has strong Python/FastAPI/PostgreSQL — prioritise Kafka and gRPC experience",
            "Look for candidates with PCI-DSS or payments compliance background",
            "High-throughput systems at 10k+ TPS is critical gap",
        ],
        "historical_insights": ["No historical data available for this position"],
        "pitfalls": [
            "Avoid candidates who only duplicate Anna's stack — team needs new capabilities",
            "Junior-to-mid candidates will struggle to mentor existing team",
            "Overly specialist Kafka engineers may lack breadth for a small team",
        ],
        "estimated_time_to_fill_days": 28,
        "confidence": 0.82,
        "confidence_level": "HIGH",
        "confidence_explanation": "Strong team context available. JD is specific. No historical hire data reduces long-term prediction quality.",
        "sources": ["Team resume: Anna Kowalski — Lead Backend", "Team resume: Piotr Wiśniewski — DevOps", "JD document"],
        "reasoning": "The team has Python/FastAPI/PostgreSQL covered by Anna Kowalski. This hire must add Kafka expertise and PCI-DSS payment compliance knowledge that the team currently lacks. The hire is clearly justified — Anna is at capacity and the team needs a senior peer, not a junior. Priority skills: Kafka, gRPC, fintech domain.",
        "key_arguments": [
            {"point": "Kafka is a genuine gap", "evidence": "No team member lists Kafka in skills", "impact": "positive"},
            {"point": "Python/FastAPI is redundant to add", "evidence": "Anna Kowalski covers Python/FastAPI at lead level", "impact": "neutral"},
            {"point": "Fintech compliance is critical", "evidence": "PCI-DSS mentioned in JD, no team member has this", "impact": "positive"},
        ],
    }, confidence=0.82)

    # ── Analysis: Mode C (Level Advisor for pos1) ─────────────────────────────
    ar_C = _analysis(db, pid, "C", [jd1.id], {
        "recommended_level": "senior",
        "level_rationale": "The role requires 5+ years with high-throughput systems and payment domain. Anna (lead) needs a peer-level engineer, not someone to mentor.",
        "alternative_levels": ["lead"],
        "seniority_signals": ["5+ years required", "PCI-DSS compliance", "System design responsibility", "Mentoring mentioned"],
        "risk_if_too_junior": "Will require significant mentoring from Anna, reducing her productivity. Cannot independently deliver high-throughput design.",
        "risk_if_too_senior": "Lead candidates may not accept peer reporting structure under Anna.",
        "confidence": 0.88,
        "confidence_level": "HIGH",
        "confidence_explanation": "JD is explicit about seniority requirements and team context shows a lead already in place.",
        "sources": ["JD: Senior Backend Engineer", "Team: Anna Kowalski Lead"],
        "reasoning": "Hire at Senior level. Lead would create org conflict with Anna. Mid would require too much mentoring at current project stage.",
        "key_arguments": [
            {"point": "Senior level aligns with 5+ years requirement", "evidence": "JD explicitly states 5+ years fintech experience", "impact": "positive"},
            {"point": "Lead role conflicts with existing structure", "evidence": "Anna Kowalski already acts as lead backend", "impact": "negative"},
        ],
    }, confidence=0.88)

    # ── Analysis: Mode E (JD Reality Check for pos1) ──────────────────────────
    ar_E = _analysis(db, pid, "E", [jd1.id], {
        "skills_vs_reality": {
            "jd_requires": ["Python", "FastAPI", "PostgreSQL", "Redis", "Docker", "REST API", "Kafka", "gRPC"],
            "team_already_has": ["Python (Anna — Lead)", "FastAPI (Anna)", "PostgreSQL (Anna)", "Redis (Anna)", "Docker (Piotr — DevOps)", "REST API (Anna)"],
            "actually_needed": ["Kafka", "gRPC", "PCI-DSS compliance", "High-throughput optimization"],
            "questionable_requirements": ["AWS Lambda — team uses EKS, not Lambda architecture"],
        },
        "workload_analysis": {
            "jd_claims": "Design payment processing microservices, ensure PCI-DSS compliance, 99.99% uptime",
            "report_reality": "Anna is handling payment core alone — weekly reports show bottlenecks at 5000 TPS, circuit breaker work pending, load testing challenges",
            "mismatches": ["JD mentions Lambda but team uses EKS exclusively", "JD underestimates throughput demands — reports show 5000+ TPS issues already"],
            "is_jd_accurate": True,
        },
        "necessity_check": {
            "is_hire_justified": True,
            "reasoning": "Anna's weekly reports confirm she is at capacity. Race condition fixes, load testing, and upcoming circuit breaker work cannot be absorbed by a 1-person backend team. Hire is critical.",
            "alternative_suggestions": ["Consider contractor for Kafka integration first to validate architecture"],
            "priority": "high",
        },
        "jd_improvement_suggestions": [
            "Remove AWS Lambda requirement — team uses EKS, Lambda experience is irrelevant",
            "Add explicit mention of 5000+ TPS throughput target to attract right candidates",
            "Specify PCI-DSS certification or hands-on compliance experience more clearly",
        ],
        "confidence": 0.87,
        "confidence_level": "HIGH",
        "confidence_explanation": "Two weekly reports available providing strong workload evidence. Team composition well-documented.",
        "sources": ["Anna weekly report W10", "Piotr weekly report W10", "Team resumes"],
        "reasoning": "JD is mostly accurate. The hire is clearly justified — Anna's reports show she is at capacity with 5000 TPS bottlenecks. Main JD issue: AWS Lambda requirement doesn't match team's EKS-based architecture.",
        "key_arguments": [
            {"point": "Hire justified by bottleneck evidence", "evidence": "Anna's report: load testing at 5000 TPS revealing bottlenecks", "impact": "positive"},
            {"point": "Lambda requirement is inaccurate", "evidence": "Piotr manages EKS — no Lambda in current stack", "impact": "negative"},
            {"point": "Kafka is critical gap not overstated", "evidence": "No team member has Kafka, async processing is pending", "impact": "positive"},
        ],
    }, confidence=0.87)

    # ── Candidate resumes ─────────────────────────────────────────────────────
    res_elena = _doc(db, pid, "elena_sokolova_resume.txt",
        "Elena Sokolova — Senior Backend Engineer\n8 years experience\nPython, FastAPI, PostgreSQL, Redis, Kafka, gRPC, Docker, AWS\nPrevious: Payment systems at Stripe EU (3 years), PCI-DSS certified\nEducation: MSc Computer Science, Kyiv Polytechnic",
        "resume",
        {"full_name": "Elena Sokolova", "email": "elena.sokolova@gmail.com", "phone": "+48 601 234 567",
         "years_of_experience": 8, "location": "Warsaw, Poland",
         "skills": ["Python", "FastAPI", "PostgreSQL", "Redis", "Kafka", "gRPC", "Docker", "AWS"],
         "work_history": [{"title": "Senior Backend Engineer", "company": "Stripe EU", "duration": "3 years", "description": "Built payment processing microservices at 50k TPS. PCI-DSS compliance implementation."}],
         "summary": "8yr backend engineer specialising in fintech. PCI-DSS certified. Kafka and gRPC expert."})

    res_david = _doc(db, pid, "david_kim_resume.txt",
        "David Kim — Backend Engineer\n5 years experience\nPython, Django, PostgreSQL, Redis, Docker, REST API\nPrevious: E-commerce backend at Samsung SDS (2 years)\nNo fintech experience",
        "resume",
        {"full_name": "David Kim", "email": "david.kim@gmail.com", "phone": "+49 176 555 0101",
         "years_of_experience": 5, "location": "Berlin, Germany",
         "skills": ["Python", "Django", "PostgreSQL", "Redis", "Docker", "REST API"],
         "summary": "5yr backend engineer. Strong Django/PostgreSQL. No payments/fintech experience."})

    res_marcin = _doc(db, pid, "marcin_zajac_resume.txt",
        "Marcin Zając — Junior-Mid Backend Developer\n2 years experience\nPython, Flask, MySQL, Git\nPrevious: Web agency intern",
        "resume",
        {"full_name": "Marcin Zając", "email": "marcin.z@outlook.pl", "phone": "+48 512 000 999",
         "years_of_experience": 2, "location": "Kraków, Poland",
         "skills": ["Python", "Flask", "MySQL", "Git"],
         "summary": "Junior developer. Limited backend experience."})

    res_yuki = _doc(db, pid, "yuki_tanaka_resume.txt",
        "Yuki Tanaka — Senior Backend Engineer\n9 years experience\nPython, FastAPI, PostgreSQL, Redis, Kafka, Kubernetes, AWS, PCI-DSS, high-throughput systems\nPrevious: Rakuten Payments Tokyo (5 years), Adyen Amsterdam (2 years)\nFluent Polish, English, Japanese",
        "resume",
        {"full_name": "Yuki Tanaka", "email": "yuki.tanaka@pm.me", "phone": "+31 6 77 88 99 00",
         "years_of_experience": 9, "location": "Amsterdam, Netherlands",
         "skills": ["Python", "FastAPI", "PostgreSQL", "Redis", "Kafka", "Kubernetes", "AWS", "PCI-DSS"],
         "work_history": [
             {"title": "Staff Engineer", "company": "Adyen", "duration": "2 years", "description": "Payment routing engine, 200k TPS peak load."},
             {"title": "Senior Backend", "company": "Rakuten Payments", "duration": "5 years", "description": "Core payment processing, PCI-DSS lead."},
         ],
         "summary": "9yr payments specialist. PCI-DSS lead. Adyen and Rakuten. Kafka expert."})

    # ── Mode D analysis results for candidates ───────────────────────────────
    ar_D_elena = _analysis(db, pid, "D", [res_elena.id, jd1.id], {
        "overall_score": 88, "verdict": "strong_fit",
        "skill_match": {"score": 92, "matched": ["Python", "FastAPI", "PostgreSQL", "Redis", "Kafka", "gRPC", "Docker"], "missing": ["gRPC production experience unclear"], "notes": "Excellent skill match. Kafka and gRPC fill team gaps."},
        "experience_match": {"score": 90, "relevant_years": 8, "notes": "8 years backend, 3 years Stripe payments. PCI-DSS certified."},
        "team_compatibility": {"score": 85, "notes": "Senior peer for Anna. Should collaborate well given similar stack."},
        "team_complementarity": {"score": 95, "fills_gaps": ["Kafka", "gRPC", "PCI-DSS compliance", "Fintech domain"], "overlaps": ["Python (Anna)", "FastAPI (Anna)", "PostgreSQL (Anna)"], "team_dynamics": "Strong peer for Anna Kowalski. Would add depth without duplication.", "recommendation": "Elena fills all genuine team gaps. Strong recommend."},
        "strengths": ["PCI-DSS certified", "Kafka expert", "Stripe payments background", "EU-based"],
        "gaps": ["gRPC — listed but needs verification", "Kubernetes depth unclear"],
        "historical_comparison": {"similar_hire": None, "project": None, "outcome": "No historical data"},
        "confidence": 0.91, "confidence_level": "HIGH",
        "confidence_explanation": "Strong resume data, clear JD match, team context available.",
        "sources": ["Elena's resume", "JD requirements", "Team skill matrix"],
        "reasoning": "Elena matches all critical JD requirements and fills Kafka/gRPC/PCI-DSS gaps that the current team lacks. She is a strong peer candidate for Anna Kowalski. Minor uncertainty around gRPC production depth.",
        "key_arguments": [
            {"point": "Fills Kafka gap perfectly", "evidence": "Resume: Kafka listed, Stripe EU experience with async processing", "impact": "positive"},
            {"point": "PCI-DSS certified", "evidence": "Resume explicitly mentions PCI-DSS certification at Stripe", "impact": "positive"},
            {"point": "Python/FastAPI overlap with Anna", "evidence": "Anna is Lead on same stack — duplication acceptable at senior level", "impact": "neutral"},
        ],
        "data_sources_used": ["resume", "jd"],
    }, confidence=0.91)

    ar_D_david = _analysis(db, pid, "D", [res_david.id, jd1.id], {
        "overall_score": 62, "verdict": "moderate_fit",
        "skill_match": {"score": 68, "matched": ["Python", "PostgreSQL", "Redis", "Docker"], "missing": ["Kafka", "gRPC", "FastAPI (uses Django)", "Fintech domain"], "notes": "Covers base stack but lacks critical differentiators."},
        "experience_match": {"score": 72, "relevant_years": 5, "notes": "5 years but all e-commerce, no payments/fintech."},
        "team_compatibility": {"score": 75, "notes": "Collaborative profile, good English."},
        "team_complementarity": {"score": 35, "fills_gaps": ["Some API design depth"], "overlaps": ["Python", "PostgreSQL", "Redis", "Docker — all covered by Anna"], "team_dynamics": "Would function more as a mid-level addition; unlikely to add senior-level architectural value.", "recommendation": "Only consider if no senior candidates available. Would need 3-6 months to get up to speed on payments."},
        "strengths": ["Solid Python fundamentals", "Good API design"],
        "gaps": ["No Kafka", "No fintech/payments domain", "Django vs FastAPI difference", "No compliance background"],
        "historical_comparison": {"similar_hire": None, "project": None, "outcome": "No data"},
        "confidence": 0.78, "confidence_level": "MEDIUM",
        "confidence_explanation": "Resume detailed but lacks fintech context data.",
        "sources": ["David's resume", "JD requirements"],
        "reasoning": "David has the right base skills but lacks the domain expertise and Kafka/gRPC experience that this hire specifically needs to fill. He adds little that Anna doesn't already cover.",
        "key_arguments": [
            {"point": "No Kafka or gRPC experience", "evidence": "Resume: no mention of Kafka or gRPC in 5 year career", "impact": "negative"},
            {"point": "No fintech domain — critical requirement", "evidence": "JD requires fintech experience; David's background is e-commerce only", "impact": "negative"},
        ],
        "data_sources_used": ["resume", "jd"],
    }, confidence=0.78)

    ar_D_marcin = _analysis(db, pid, "D", [res_marcin.id, jd1.id], {
        "overall_score": 28, "verdict": "not_recommended",
        "skill_match": {"score": 25, "matched": ["Python"], "missing": ["FastAPI", "PostgreSQL", "Redis", "Kafka", "gRPC", "Docker", "Fintech"], "notes": "Severely under-qualified. Flask/MySQL experience is far below requirements."},
        "experience_match": {"score": 20, "relevant_years": 2, "notes": "2 years vs 5+ required. Web agency work is not applicable."},
        "team_compatibility": {"score": 60, "notes": "No red flags personality-wise."},
        "team_complementarity": {"score": 10, "fills_gaps": [], "overlaps": ["Python (basic)"], "team_dynamics": "Would require extensive mentoring from Anna, significantly reducing her capacity.", "recommendation": "Not suitable. Consider for a junior role in a different project."},
        "strengths": ["Python basics", "Eager learner based on notes"],
        "gaps": ["Virtually every technical requirement is missing", "2 years experience vs 5+ required", "No fintech, no Kafka, no Kubernetes"],
        "historical_comparison": {"similar_hire": None, "project": None, "outcome": "No data"},
        "confidence": 0.95, "confidence_level": "HIGH",
        "confidence_explanation": "Clear mismatch — high confidence in negative recommendation.",
        "sources": ["Marcin's resume", "JD requirements"],
        "reasoning": "Marcin is a junior developer with 2 years experience, primarily web agency work. The role requires 5+ years and payment systems expertise. This is not a close call.",
        "key_arguments": [
            {"point": "Experience gap: 2 years vs 5+ required", "evidence": "Resume: 2 years total experience, intern role at web agency", "impact": "negative"},
            {"point": "Missing all key technical skills", "evidence": "Flask/MySQL vs FastAPI/PostgreSQL/Redis/Kafka required", "impact": "negative"},
        ],
        "data_sources_used": ["resume", "jd"],
    }, confidence=0.95)

    ar_D_yuki = _analysis(db, pid, "D", [res_yuki.id, jd1.id], {
        "overall_score": 96, "verdict": "strong_fit",
        "skill_match": {"score": 98, "matched": ["Python", "FastAPI", "PostgreSQL", "Redis", "Kafka", "Kubernetes", "AWS", "PCI-DSS"], "missing": [], "notes": "Perfect skill match. Exceeds requirements across the board."},
        "experience_match": {"score": 97, "relevant_years": 9, "notes": "9 years, Adyen + Rakuten — direct payments experience at 200k TPS scale."},
        "team_compatibility": {"score": 88, "notes": "EU-based, English fluent, collaborative background."},
        "team_complementarity": {"score": 99, "fills_gaps": ["Kafka", "gRPC", "PCI-DSS", "High-throughput (200k TPS)", "Adyen-grade fintech expertise"], "overlaps": ["Python", "FastAPI", "PostgreSQL — but at higher scale level"], "team_dynamics": "Would operate as a true senior peer to Anna, potentially advancing to a co-lead role. Adds transformative fintech depth.", "recommendation": "Exceptional candidate. Prioritise closing offer immediately."},
        "strengths": ["Adyen and Rakuten experience — world-class fintech", "200k TPS proven at Adyen", "PCI-DSS lead experience", "EU-based"],
        "gaps": ["May expect higher rate than budget allows"],
        "historical_comparison": {"similar_hire": None, "project": None, "outcome": "No data"},
        "confidence": 0.97, "confidence_level": "HIGH",
        "confidence_explanation": "Exceptional resume quality, direct domain match, team context confirms all gaps filled.",
        "sources": ["Yuki's resume", "JD", "Team skills matrix"],
        "reasoning": "Yuki is an exceptional match. 9 years payments at Adyen and Rakuten, PCI-DSS lead, Kafka expert. Fills all team gaps and brings capabilities (200k TPS scale) that current team cannot replicate. Highest priority candidate.",
        "key_arguments": [
            {"point": "Adyen experience is directly applicable", "evidence": "200k TPS payment routing at Adyen — exact use case for Novex", "impact": "positive"},
            {"point": "Fills every technical gap", "evidence": "Kafka, gRPC, PCI-DSS, high-throughput — all confirmed in resume", "impact": "positive"},
            {"point": "Rate risk", "evidence": "Adyen/Rakuten background may expect €12k+/month", "impact": "negative"},
        ],
        "data_sources_used": ["resume", "jd", "reports"],
    }, confidence=0.97)

    # ── Candidates ────────────────────────────────────────────────────────────
    c1 = _candidate(db, pos1.id, "Elena Sokolova", "elena.sokolova@gmail.com", "+48 601 234 567", "Warsaw, Poland", 8,
                    "technical_interview", 88.0, "strong_fit", ar_D_elena.id, res_elena.id,
                    recruiter_notes="Strong profile. PCI-DSS certified. Scheduled for technical deep dive.",
                    interview_notes="Excellent system design. Explained Kafka at Stripe in detail. Answered all throughput questions well.",
                    tags=["fintech", "kafka", "pci-dss"],
                    candidate_rate=9500.0, candidate_rate_period="monthly")

    c2 = _candidate(db, pos1.id, "David Kim", "david.kim@gmail.com", "+49 176 555 0101", "Berlin, Germany", 5,
                    "screening", 62.0, "moderate_fit", ar_D_david.id, res_david.id,
                    recruiter_notes="Decent base skills. Lacks fintech. Moved to screening for further evaluation.",
                    tags=["backend", "django"],
                    candidate_rate=7200.0, candidate_rate_period="monthly")

    c3 = _candidate(db, pos1.id, "Marcin Zając", "marcin.z@outlook.pl", "+48 512 000 999", "Kraków, Poland", 2,
                    "rejected", 28.0, "not_recommended", ar_D_marcin.id, res_marcin.id,
                    recruiter_notes="Junior profile submitted by mistake.",
                    rejection_reason="Does not meet minimum 5 years experience requirement. Missing all key technical skills.",
                    tags=["junior", "rejected-experience"],
                    candidate_rate=3500.0, candidate_rate_period="monthly")

    c4 = _candidate(db, pos1.id, "Yuki Tanaka", "yuki.tanaka@pm.me", "+31 6 77 88 99 00", "Amsterdam, Netherlands", 9,
                    "offer", 96.0, "strong_fit", ar_D_yuki.id, res_yuki.id,
                    recruiter_notes="Top candidate. Adyen + Rakuten. Offer extended at $11,500/month.",
                    interview_notes="Technical: exceptional. Designed circuit breaker pattern on whiteboard. Kafka architecture clear.",
                    client_feedback="Client very happy. Wants Yuki to start ASAP.",
                    tags=["fintech", "kafka", "adyen", "top-candidate"],
                    candidate_rate=11500.0, candidate_rate_period="monthly")

    db.commit()
    print(f"Project 1 created: {p1.name} (id={pid}) | 3 team | 2 positions | 4 candidates")

finally:
    db.close()


# ═════════════════════════════════════════════════════════════════════════════
# PROJECT 2: MedCore Systems — Patient Data Platform
# ═════════════════════════════════════════════════════════════════════════════
db = SessionLocal()
try:
    p2 = Project(
        name="MedCore Systems — Patient Data Platform",
        client_name="MedCore Systems SA",
        description="GDPR-compliant patient data warehouse. Python/Spark stack, 4-person team. Hiring ML Engineer (urgent) and Data Architect.",
        status="active",
    )
    db.add(p2)
    db.flush()
    pid = p2.id

    # ── Team ─────────────────────────────────────────────────────────────────
    tm4_res = _doc(db, pid, "james_wilson_resume.txt",
        "James Wilson — Senior Data Engineer\n7 years. Python, Spark, Databricks, Airflow, Delta Lake, SQL, AWS Glue\nBuilds ETL pipelines for patient records.",
        "resume",
        {"full_name": "James Wilson", "email": "james@medcore.io", "years_of_experience": 7,
         "skills": ["Python", "Spark", "Databricks", "Airflow", "Delta Lake", "SQL", "AWS Glue"],
         "summary": "Senior data engineer. ETL pipelines for healthcare data."})

    tm5_res = _doc(db, pid, "sofia_hernandez_resume.txt",
        "Sofia Hernandez — Mid Backend Engineer\n4 years. Python, Django, PostgreSQL, Celery, Docker, REST\nMaintains patient API layer.",
        "resume",
        {"full_name": "Sofia Hernandez", "email": "sofia@medcore.io", "years_of_experience": 4,
         "skills": ["Python", "Django", "PostgreSQL", "Celery", "Docker", "REST"],
         "summary": "Backend API developer for healthcare platform."})

    tm6_res = _doc(db, pid, "tomasz_kaczmarek_resume.txt",
        "Tomasz Kaczmarek — Junior Frontend\n1.5 years. Vue.js, JavaScript, CSS, HTML\nBuilds patient portal UI.",
        "resume",
        {"full_name": "Tomasz Kaczmarek", "email": "tomasz@medcore.io", "years_of_experience": 1.5,
         "skills": ["Vue.js", "JavaScript", "CSS", "HTML"],
         "summary": "Junior frontend developer."})

    tm7_res = _doc(db, pid, "laura_chen_resume.txt",
        "Laura Chen — Lead Architect\n12 years. Python, AWS, Microservices, Kafka, Event Sourcing, GDPR compliance, Data governance\nDesigns platform architecture.",
        "resume",
        {"full_name": "Laura Chen", "email": "laura@medcore.io", "years_of_experience": 12,
         "skills": ["Python", "AWS", "Microservices", "Kafka", "Event Sourcing", "GDPR compliance", "Data governance"],
         "summary": "Lead architect. GDPR/data governance expert. 12yr experience."})

    tm4 = TeamMember(project_id=pid, name="James Wilson", role="Senior Data Engineer",
                     level="senior",
                     skills=["Python", "Spark", "Databricks", "Airflow", "Delta Lake", "SQL"],
                     resume_document_id=tm4_res.id, status="active", start_date=_days_ago(400))
    tm5 = TeamMember(project_id=pid, name="Sofia Hernandez", role="Mid Backend Developer",
                     level="mid",
                     skills=["Python", "Django", "PostgreSQL", "Celery", "Docker"],
                     resume_document_id=tm5_res.id, status="active", start_date=_days_ago(250))
    tm6 = TeamMember(project_id=pid, name="Tomasz Kaczmarek", role="Junior Frontend Developer",
                     level="junior",
                     skills=["Vue.js", "JavaScript", "CSS"],
                     resume_document_id=tm6_res.id, status="active", start_date=_days_ago(100))
    tm7 = TeamMember(project_id=pid, name="Laura Chen", role="Lead Architect",
                     level="lead",
                     skills=["Python", "AWS", "Kafka", "Microservices", "GDPR compliance", "Data governance"],
                     resume_document_id=tm7_res.id, status="active", start_date=_days_ago(500))
    db.add_all([tm4, tm5, tm6, tm7])
    db.flush()

    # Weekly reports
    rep3 = _doc(db, pid, "james_weekly_w9.txt",
        "Weekly Report — James Wilson — Week 9\nCompleted: Migrated 3 ETL pipelines from Glue to Databricks, fixed Delta Lake MERGE performance issue (5x speedup), onboarded new S3 data source for lab results.\nBlockers: ML feature engineering backlog growing — no ML engineer to consume clean data.\nNext week: Implement data quality checks, begin model feature store design.",
        "report",
        {"developer_name": "James Wilson", "week": "W9", "tasks_completed": ["ETL migration", "Delta Lake fix", "S3 source"], "blockers": ["ML feature engineering backlog — no ML engineer"]})
    rep3.team_member_id = tm4.id

    rep4 = _doc(db, pid, "laura_weekly_w9.txt",
        "Weekly Report — Laura Chen — Week 9\nCompleted: Architecture review for ML pipeline integration, GDPR data lineage documentation, compliance audit prep.\nChallenges: Cannot proceed with ML model deployment without dedicated ML engineer.\nNext: Data governance framework v2, model registry design.",
        "report",
        {"developer_name": "Laura Chen", "week": "W9", "tasks_completed": ["architecture review", "GDPR lineage", "compliance audit"], "blockers": ["ML deployment blocked — no ML engineer"]})
    rep4.team_member_id = tm7.id

    # JDs
    jd3 = _doc(db, pid, "ml_engineer_jd.txt",
        "Job Description: ML Engineer\nClient: MedCore Systems SA\nRequired: Python, PyTorch or TensorFlow, scikit-learn, MLflow or similar, Feature engineering, SQL\nNice to have: Spark MLlib, Databricks, AWS SageMaker, Healthcare ML\nExperience: 4+ years ML engineering\nResponsibilities: Build and deploy ML models for patient risk scoring, anomaly detection, work with data engineering team, GDPR-compliant model development.\nSalary: €7,000-10,000/month",
        "jd",
        {"title": "ML Engineer", "required_skills": ["Python", "PyTorch", "TensorFlow", "scikit-learn", "MLflow", "Feature engineering", "SQL"],
         "preferred_skills": ["Spark MLlib", "Databricks", "AWS SageMaker", "Healthcare ML"],
         "requirements": ["4+ years ML experience", "Model deployment experience", "GDPR awareness"],
         "seniority_level": "senior", "location": "Remote (EU)", "employment_type": "B2B",
         "salary_range": "€7,000-10,000/month"})

    jd4 = _doc(db, pid, "data_architect_jd.txt",
        "Job Description: Data Architect\nRequired: Data modelling, dbt, Spark, Data governance, SQL, Cloud (AWS/GCP)\nExperience: 6+ years data architecture\nResponsibilities: Design data warehouse schema, implement data governance framework, work with Laura Chen.",
        "jd",
        {"title": "Data Architect", "required_skills": ["Data modelling", "dbt", "Spark", "Data governance", "SQL", "AWS"],
         "seniority_level": "lead", "employment_type": "B2B"})

    pos3 = Position(project_id=pid, title="ML Engineer", level="senior",
                    status="open", jd_document_id=jd3.id,
                    client_rate=13000.0, client_rate_currency="USD", client_rate_period="monthly",
                    created_at=_days_ago(22))
    pos4 = Position(project_id=pid, title="Data Architect", level="lead",
                    status="open", jd_document_id=jd4.id,
                    created_at=_days_ago(8))
    db.add_all([pos3, pos4])
    db.flush()

    # Mode A for ML Engineer JD
    ar_A2 = _analysis(db, pid, "A", [jd3.id], {
        "skills_required": [
            {"name": "Python", "criticality": "nice", "notes": "Team has Python (James, Sofia, Laura) — not a differentiator"},
            {"name": "PyTorch/TensorFlow", "criticality": "must", "notes": "Zero ML framework coverage on team"},
            {"name": "MLflow", "criticality": "must", "notes": "No model registry in team"},
            {"name": "Feature engineering", "criticality": "must", "notes": "James has data pipeline but no ML feature engineering"},
            {"name": "Spark MLlib", "criticality": "nice", "notes": "James has Spark — overlap acceptable"},
            {"name": "Healthcare ML", "criticality": "must", "notes": "Critical for GDPR-compliant patient data models"},
        ],
        "search_guidance": [
            "Team has Spark/Python/data engineering covered — focus on ML modelling and deployment skills",
            "GDPR-aware ML is rare — prioritise candidates with healthcare or regulated data experience",
            "MLflow or similar model registry experience is critical",
        ],
        "historical_insights": ["No historical data available"],
        "pitfalls": ["Data engineers without ML deployment experience will not fill the gap", "MLOps-only candidates may lack modelling depth"],
        "estimated_time_to_fill_days": 35,
        "confidence": 0.85,
        "confidence_level": "HIGH",
        "confidence_explanation": "Strong team context available. Weekly reports confirm urgency.",
        "sources": ["Team resumes", "Weekly reports (James, Laura)", "JD document"],
        "reasoning": "The team has strong data engineering (James) but zero ML coverage. Weekly reports from James and Laura confirm ML deployment is blocked. Priority: PyTorch/MLflow and healthcare compliance experience.",
        "key_arguments": [
            {"point": "ML is the only missing capability", "evidence": "James/Laura weekly reports explicitly state 'blocked — no ML engineer'", "impact": "positive"},
            {"point": "Healthcare ML compliance is critical", "evidence": "GDPR patient data — requires specialist, not generic ML engineer", "impact": "positive"},
        ],
    }, confidence=0.85)

    # Mode E for ML Engineer JD
    ar_E2 = _analysis(db, pid, "E", [jd3.id], {
        "skills_vs_reality": {
            "jd_requires": ["Python", "PyTorch", "TensorFlow", "scikit-learn", "MLflow", "SQL", "Spark MLlib"],
            "team_already_has": ["Python (James, Sofia, Laura)", "Spark (James)", "SQL (James)"],
            "actually_needed": ["PyTorch/TensorFlow", "MLflow", "Healthcare ML", "Feature engineering for patient data", "Model deployment"],
            "questionable_requirements": ["AWS SageMaker — team uses Databricks, not SageMaker"],
        },
        "workload_analysis": {
            "jd_claims": "Build and deploy ML models for patient risk scoring and anomaly detection",
            "report_reality": "James is building feature pipelines but has no ML consumer. Laura is designing model registry but has no ML engineer to fill it. Both reports confirm this is a critical gap.",
            "mismatches": ["SageMaker mentioned but team uses Databricks exclusively"],
            "is_jd_accurate": True,
        },
        "necessity_check": {
            "is_hire_justified": True,
            "reasoning": "Both James and Laura's weekly reports explicitly cite ML engineer absence as a blocker. Feature data is ready but has no consumer. Architecture is designed but cannot be executed.",
            "alternative_suggestions": [],
            "priority": "critical",
        },
        "jd_improvement_suggestions": [
            "Replace AWS SageMaker with Databricks MLflow — aligns with actual stack",
            "Add GDPR-compliant ML/data privacy experience as explicit requirement",
        ],
        "confidence": 0.91,
        "confidence_level": "HIGH",
        "confidence_explanation": "Two team reports confirm critical bottleneck. Team composition well-documented.",
        "sources": ["James weekly W9", "Laura weekly W9"],
        "reasoning": "Hire is critical and justified. Two independent team reports confirm the same blocker. The JD is accurate except for the SageMaker requirement which doesn't match the Databricks stack.",
        "key_arguments": [
            {"point": "ML deployment is blocked by absence of this role", "evidence": "James W9: 'ML feature engineering backlog'; Laura W9: 'ML deployment blocked'", "impact": "positive"},
            {"point": "SageMaker requirement is wrong", "evidence": "Piotr and James use Databricks — SageMaker is not in the stack", "impact": "negative"},
        ],
    }, confidence=0.91)

    # Candidate resumes + scores
    res_alex = _doc(db, pid, "alex_petrov_resume.txt",
        "Alex Petrov — ML Engineer\n5 years. Python, PyTorch, scikit-learn, MLflow, SQL, Airflow, Docker\nPrevious: NLP at VTB Bank (fintech ML), anomaly detection models for fraud.\nNo healthcare experience.",
        "resume",
        {"full_name": "Alex Petrov", "email": "alex.petrov@gmail.com", "years_of_experience": 5,
         "skills": ["Python", "PyTorch", "scikit-learn", "MLflow", "SQL", "Airflow", "Docker"],
         "summary": "ML engineer. Fintech ML specialist, anomaly detection expert."})

    res_maria = _doc(db, pid, "maria_santos_resume.txt",
        "Maria Santos — Senior ML Engineer\n7 years. Python, PyTorch, TensorFlow, MLflow, Databricks, Spark MLlib, Healthcare ML, GDPR compliance\nPrevious: Patient risk scoring at Siemens Healthineers (3 years), NLP at Philips Healthcare (2 years)\nPhD Medical Informatics",
        "resume",
        {"full_name": "Maria Santos", "email": "maria.santos@proton.me", "years_of_experience": 7,
         "skills": ["Python", "PyTorch", "TensorFlow", "MLflow", "Databricks", "Spark MLlib", "Healthcare ML", "GDPR"],
         "work_history": [
             {"title": "Senior ML Engineer", "company": "Siemens Healthineers", "duration": "3 years", "description": "Patient risk scoring models deployed to 50 hospitals."},
             {"title": "ML Engineer", "company": "Philips Healthcare", "duration": "2 years", "description": "NLP for clinical notes, GDPR-compliant data pipeline."},
         ],
         "summary": "PhD-level ML for healthcare. GDPR-native ML development. Databricks expert."})

    res_boris = _doc(db, pid, "boris_kovalev_resume.txt",
        "Boris Kovalev — Data Analyst\n3 years. Python, pandas, Excel, SQL, Power BI\nPrevious: Business analyst at supermarket chain\nNo ML engineering experience.",
        "resume",
        {"full_name": "Boris Kovalev", "email": "boris.k@mail.ru", "years_of_experience": 3,
         "skills": ["Python", "pandas", "SQL", "Excel", "Power BI"],
         "summary": "Data analyst. No ML engineering background."})

    ar_D_alex = _analysis(db, pid, "D", [res_alex.id, jd3.id], {
        "overall_score": 75, "verdict": "moderate_fit",
        "skill_match": {"score": 78, "matched": ["Python", "PyTorch", "scikit-learn", "MLflow", "SQL", "Airflow"], "missing": ["Databricks", "Healthcare ML", "GDPR-aware ML"], "notes": "Good ML skills but no healthcare domain."},
        "experience_match": {"score": 80, "relevant_years": 5, "notes": "5 years ML, strong fraud/fintech. Healthcare gap is significant."},
        "team_complementarity": {"score": 70, "fills_gaps": ["PyTorch", "MLflow", "anomaly detection"], "overlaps": ["Python", "Airflow (James)"], "team_dynamics": "Good addition. Would benefit from Laura's architecture guidance.", "recommendation": "Recommend with caveat — healthcare domain training required."},
        "strengths": ["MLflow expert", "Anomaly detection matches JD requirement", "Production ML deployment experience"],
        "gaps": ["No healthcare ML", "No GDPR ML compliance", "No Databricks"],
        "confidence": 0.80, "confidence_level": "HIGH",
        "confidence_explanation": "Resume clear, JD specific.", "sources": ["Alex's resume", "JD"],
        "reasoning": "Alex has solid ML engineering skills and MLflow expertise. Main gap is healthcare domain and GDPR compliance. His fintech anomaly detection is partially transferable.",
        "key_arguments": [
            {"point": "MLflow expertise matches requirement", "evidence": "Resume: MLflow listed with production deployment at VTB", "impact": "positive"},
            {"point": "No healthcare experience — critical requirement", "evidence": "JD requires healthcare ML; Alex has fintech background only", "impact": "negative"},
        ],
        "data_sources_used": ["resume", "jd"],
    }, confidence=0.80)

    ar_D_maria = _analysis(db, pid, "D", [res_maria.id, jd3.id], {
        "overall_score": 98, "verdict": "strong_fit",
        "skill_match": {"score": 99, "matched": ["Python", "PyTorch", "TensorFlow", "MLflow", "Databricks", "Spark MLlib", "Healthcare ML", "GDPR"], "missing": [], "notes": "Perfect match. All required and preferred skills present."},
        "experience_match": {"score": 99, "relevant_years": 7, "notes": "PhD + 7 years healthcare ML. Siemens and Philips are top-tier references."},
        "team_complementarity": {"score": 99, "fills_gaps": ["PyTorch", "TensorFlow", "MLflow", "Healthcare ML", "GDPR-aware ML", "Databricks ML"], "overlaps": ["Python", "Spark (James at data level)"], "team_dynamics": "Would work seamlessly with James on data→features→models pipeline. Laura's architecture expertise aligns perfectly.", "recommendation": "Hire immediately. Exceptional candidate who fills every gap."},
        "strengths": ["PhD healthcare ML", "Databricks native", "GDPR ML compliance certified", "Siemens Healthineers — world-class reference"],
        "gaps": ["May expect very high rate"],
        "confidence": 0.99, "confidence_level": "HIGH",
        "confidence_explanation": "Zero ambiguity. Perfect match on all dimensions.",
        "sources": ["Maria's resume", "JD", "Team context"],
        "reasoning": "Maria is an exceptional and rare candidate. She is exactly what this project needs — PhD-level healthcare ML with GDPR compliance built-in. Siemens Healthineers deployment experience directly matches the JD.",
        "key_arguments": [
            {"point": "Siemens Healthineers — directly applicable experience", "evidence": "Patient risk scoring deployed to 50 hospitals — exact JD requirement", "impact": "positive"},
            {"point": "GDPR-compliant ML — rare and required", "evidence": "Philips Healthcare NLP with GDPR data pipeline", "impact": "positive"},
            {"point": "Databricks proficiency matches team stack", "evidence": "Resume: Databricks listed; James uses Databricks for ETL", "impact": "positive"},
        ],
        "data_sources_used": ["resume", "jd", "reports"],
    }, confidence=0.99)

    ar_D_boris = _analysis(db, pid, "D", [res_boris.id, jd3.id], {
        "overall_score": 18, "verdict": "not_recommended",
        "skill_match": {"score": 15, "matched": ["Python (basic)", "SQL"], "missing": ["PyTorch", "TensorFlow", "MLflow", "ML modelling", "Databricks", "Healthcare ML", "GDPR"], "notes": "Data analyst, not ML engineer. Wrong profile entirely."},
        "experience_match": {"score": 20, "relevant_years": 0, "notes": "3 years data analysis — not ML engineering. Business analyst background not transferable."},
        "team_complementarity": {"score": 5, "fills_gaps": [], "overlaps": ["Python (basic)", "SQL — covered by entire team"], "team_dynamics": "Would not contribute ML capabilities at all.", "recommendation": "Not suitable. Wrong profile for this role."},
        "strengths": ["Some Python and SQL"],
        "gaps": ["Not an ML engineer — completely wrong profile", "No model development experience", "Power BI/Excel background is analytics, not ML"],
        "confidence": 0.98, "confidence_level": "HIGH",
        "confidence_explanation": "Clear mismatch.", "sources": ["Boris's resume", "JD"],
        "reasoning": "Boris is a data analyst, not an ML engineer. His Power BI and Excel background is from business analytics. This is not a borderline case — wrong profile entirely.",
        "key_arguments": [
            {"point": "Data analyst vs ML engineer — fundamentally wrong profile", "evidence": "Resume: Power BI, Excel — analytics tools, not ML", "impact": "negative"},
        ],
        "data_sources_used": ["resume", "jd"],
    }, confidence=0.98)

    _candidate(db, pos3.id, "Alex Petrov", "alex.petrov@gmail.com", "+7 916 777 88 99", "Berlin, Germany", 5,
               "client_interview", 75.0, "moderate_fit", ar_D_alex.id, res_alex.id,
               recruiter_notes="Good ML skills. Healthcare training needed. Client agreed to proceed.",
               interview_notes="Technical strong. Discussed anomaly detection approach. Healthcare gap acknowledged.",
               client_feedback="Interesting candidate. Concerns about healthcare domain — approved for final round.",
               tags=["ml", "fintech-ml", "anomaly-detection"],
               candidate_rate=8500.0)

    _candidate(db, pos3.id, "Maria Santos", "maria.santos@proton.me", "+34 600 111 222", "Barcelona, Spain", 7,
               "hired", 98.0, "strong_fit", ar_D_maria.id, res_maria.id,
               recruiter_notes="Exceptional. PhD Healthcare ML. Offer accepted €9,500/month.",
               interview_notes="Outstanding. Presented patient risk scoring architecture in detail. GDPR compliance deep knowledge.",
               client_feedback="Perfect candidate. Client very excited. Wants immediate start.",
               tags=["healthcare-ml", "phd", "databricks", "top-candidate"],
               candidate_rate=9500.0, availability="Immediate")

    _candidate(db, pos3.id, "Boris Kovalev", "boris.k@mail.ru", "+7 999 000 1122", "Moscow, Russia", 3,
               "rejected", 18.0, "not_recommended", ar_D_boris.id, res_boris.id,
               recruiter_notes="Applied as ML engineer — is a data analyst.",
               rejection_reason="Wrong profile. Data analyst, not ML engineer. Applied to wrong position.",
               tags=["wrong-profile", "analyst"],
               candidate_rate=2800.0)

    db.commit()
    print(f"Project 2 created: {p2.name} (id={pid}) | 4 team | 2 positions | 3 candidates")

finally:
    db.close()


# ═════════════════════════════════════════════════════════════════════════════
# PROJECT 3: CloudStack — DevOps Transformation (AT RISK — 35 days open)
# ═════════════════════════════════════════════════════════════════════════════
db = SessionLocal()
try:
    p3 = Project(
        name="CloudStack — DevOps Transformation",
        client_name="CloudStack Ltd",
        description="Kubernetes-native platform modernisation. 2-person team. Platform Engineer position open 35 days — at risk.",
        status="active",
    )
    db.add(p3)
    db.flush()
    pid = p3.id

    # ── Team ─────────────────────────────────────────────────────────────────
    tm8_res = _doc(db, pid, "ryan_obrien_resume.txt",
        "Ryan O'Brien — Senior DevOps Engineer\n6 years. Docker, Kubernetes, Terraform, Azure, Azure DevOps, Helm, ArgoCD, GitOps\nManages client Azure AKS cluster.",
        "resume",
        {"full_name": "Ryan O'Brien", "email": "ryan@cloudstack.io", "years_of_experience": 6,
         "skills": ["Docker", "Kubernetes", "Terraform", "Azure", "Azure DevOps", "Helm", "ArgoCD", "GitOps"],
         "summary": "DevOps/platform engineer. Azure Kubernetes specialist."})

    tm9_res = _doc(db, pid, "priya_sharma_resume.txt",
        "Priya Sharma — Mid Backend Engineer\n3 years. Python, Go, PostgreSQL, gRPC, Docker, Redis\nBuilds internal tooling and platform APIs.",
        "resume",
        {"full_name": "Priya Sharma", "email": "priya@cloudstack.io", "years_of_experience": 3,
         "skills": ["Python", "Go", "PostgreSQL", "gRPC", "Docker", "Redis"],
         "summary": "Platform engineer building internal tooling in Go and Python."})

    tm8 = TeamMember(project_id=pid, name="Ryan O'Brien", role="Senior DevOps Engineer",
                     level="senior",
                     skills=["Docker", "Kubernetes", "Terraform", "Azure", "Helm", "ArgoCD", "GitOps"],
                     resume_document_id=tm8_res.id, status="active", start_date=_days_ago(180))
    tm9 = TeamMember(project_id=pid, name="Priya Sharma", role="Mid Backend Engineer",
                     level="mid",
                     skills=["Python", "Go", "PostgreSQL", "gRPC", "Docker", "Redis"],
                     resume_document_id=tm9_res.id, status="active", start_date=_days_ago(120))
    db.add_all([tm8, tm9])
    db.flush()

    # Reports
    rep5 = _doc(db, pid, "ryan_weekly_w8.txt",
        "Weekly Report — Ryan O'Brien — Week 8\nCompleted: Set up cluster autoscaler, implemented node pool separation for prod/staging, created Terraform modules for new client onboarding.\nChallenges: Handling both infra ops and platform development simultaneously — burnout risk. Need Platform Engineer.\nNext: Multi-cluster federation design.",
        "report",
        {"developer_name": "Ryan O'Brien", "week": "W8", "tasks_completed": ["cluster autoscaler", "node pool separation", "Terraform modules"], "blockers": ["Handling infra+platform dev alone — burnout risk"]})
    rep5.team_member_id = tm8.id

    rep6 = _doc(db, pid, "priya_weekly_w8.txt",
        "Weekly Report — Priya Sharma — Week 8\nCompleted: Finished internal CLI tooling, gRPC service mesh prototype, Go-based admission webhook.\nChallenges: Platform API work slowing due to lack of dedicated platform engineer. Ryan overloaded.\nNext: Service mesh observability, Prometheus integration.",
        "report",
        {"developer_name": "Priya Sharma", "week": "W8", "tasks_completed": ["CLI tooling", "gRPC service mesh", "admission webhook"], "blockers": ["Ryan overloaded — platform work blocked"]})
    rep6.team_member_id = tm9.id

    # JD
    jd5 = _doc(db, pid, "platform_engineer_jd.txt",
        "Job Description: Platform Engineer\nClient: CloudStack Ltd\nRequired: Kubernetes (CKA preferred), Terraform, CI/CD (GitLab or GitHub Actions), Helm, Docker, Go or Python\nNice to have: ArgoCD, Service mesh (Istio/Linkerd), Observability (Prometheus, Grafana, Jaeger)\nExperience: 4+ years platform/devops, 2+ years Kubernetes\nResponsibilities: Build and maintain internal developer platform, IDP tooling, Kubernetes operator development, enable 30 engineering teams.\nSalary: $7,000-11,000/month",
        "jd",
        {"title": "Platform Engineer", "required_skills": ["Kubernetes", "Terraform", "CI/CD", "Helm", "Docker", "Go", "Python"],
         "preferred_skills": ["ArgoCD", "Istio", "Linkerd", "Prometheus", "Grafana"],
         "requirements": ["4+ years platform engineering", "2+ years Kubernetes", "IDP experience preferred"],
         "seniority_level": "senior", "location": "Remote", "employment_type": "B2B",
         "salary_range": "$7,000-11,000/month"})

    pos5 = Position(project_id=pid, title="Platform Engineer", level="senior",
                    status="open", jd_document_id=jd5.id,
                    client_rate=13500.0, client_rate_currency="USD", client_rate_period="monthly",
                    created_at=_days_ago(35))
    db.add(pos5)
    db.flush()

    # Mode A
    ar_A3 = _analysis(db, pid, "A", [jd5.id], {
        "skills_required": [
            {"name": "Kubernetes", "criticality": "nice", "notes": "Ryan has Kubernetes but is overloaded — another Kubernetes engineer is additive"},
            {"name": "Terraform", "criticality": "nice", "notes": "Ryan has Terraform — candidate must extend, not duplicate"},
            {"name": "Go", "criticality": "must", "notes": "Priya has some Go but needs a dedicated Go platform developer"},
            {"name": "ArgoCD/GitOps", "criticality": "must", "notes": "Ryan has ArgoCD setup but needs dedicated platform owner"},
            {"name": "Istio/Service mesh", "criticality": "must", "notes": "Priya is doing service mesh prototype — needs senior platform input"},
            {"name": "Kubernetes Operators", "criticality": "must", "notes": "No operator development capability on team currently"},
        ],
        "search_guidance": [
            "Team has Kubernetes/Terraform/ArgoCD — look for IDP and Kubernetes Operators specifically",
            "Go platform development is critical — Python alone insufficient",
            "35 days open — consider relaxing some nice-to-have requirements to close faster",
        ],
        "historical_insights": ["No historical data available"],
        "pitfalls": ["Pure DevOps without platform/SRE experience won't fill gap", "Position open 35 days — urgency is high"],
        "estimated_time_to_fill_days": 21,
        "confidence": 0.86,
        "confidence_level": "HIGH",
        "confidence_explanation": "Good team context from two reports. Position urgency confirmed.",
        "sources": ["Ryan weekly W8", "Priya weekly W8", "Team resumes", "JD"],
        "reasoning": "The team has Kubernetes and Terraform covered but Ryan is at burnout risk handling both ops and platform work. The hire is urgent (35 days open) and must add Kubernetes Operators and IDP development specifically. Go expertise is critical.",
        "key_arguments": [
            {"point": "Ryan burnout risk is documented", "evidence": "Ryan W8: 'handling infra ops and platform dev simultaneously — burnout risk'", "impact": "positive"},
            {"point": "Kubernetes Operator development is missing", "evidence": "No team member has operator development experience", "impact": "positive"},
            {"point": "35 days open — urgency high", "evidence": "Position age and team reports both confirm critical gap", "impact": "positive"},
        ],
    }, confidence=0.86)

    # Mode E
    ar_E3 = _analysis(db, pid, "E", [jd5.id], {
        "skills_vs_reality": {
            "jd_requires": ["Kubernetes", "Terraform", "Helm", "Docker", "Go", "CI/CD", "ArgoCD"],
            "team_already_has": ["Kubernetes (Ryan)", "Terraform (Ryan)", "Helm (Ryan)", "Docker (Ryan, Priya)", "ArgoCD (Ryan)", "Go basics (Priya)"],
            "actually_needed": ["Kubernetes Operators", "IDP tooling", "Advanced Go platform development", "Multi-cluster federation"],
            "questionable_requirements": ["CKA certification — Ryan doesn't have it and manages cluster fine"],
        },
        "workload_analysis": {
            "jd_claims": "Build internal developer platform, IDP tooling, Kubernetes operator development",
            "report_reality": "Ryan is doing both infra ops and platform development. Priya is doing service mesh prototyping. Both report burnout risk and platform work being blocked.",
            "mismatches": ["CKA certification not relevant to actual work", "JD doesn't mention multi-cluster federation which is the key upcoming challenge"],
            "is_jd_accurate": True,
        },
        "necessity_check": {
            "is_hire_justified": True,
            "reasoning": "Position open 35 days. Ryan's report explicitly mentions burnout risk. Priya confirms platform work is blocked. This hire cannot wait — infrastructure risk is real.",
            "alternative_suggestions": ["Interim contractor for Kubernetes Operators while full hire proceeds"],
            "priority": "critical",
        },
        "jd_improvement_suggestions": [
            "Add multi-cluster federation explicitly — it is the next major deliverable",
            "Remove CKA requirement — not relevant and reduces candidate pool unnecessarily",
            "Emphasise IDP (Internal Developer Platform) experience — this differentiates from generic DevOps",
        ],
        "confidence": 0.89,
        "confidence_level": "HIGH",
        "confidence_explanation": "Two reports confirm burnout risk. 35-day position age adds urgency evidence.",
        "sources": ["Ryan weekly W8", "Priya weekly W8"],
        "reasoning": "Hire is critical and overdue. Both team reports confirm the gap. JD is mostly accurate but undersells the urgency and includes an irrelevant CKA requirement that reduces candidate pool.",
        "key_arguments": [
            {"point": "35 days open = critical threshold", "evidence": "Position age exceeds critical 30-day mark", "impact": "negative"},
            {"point": "Both team members report blocked work", "evidence": "Ryan: burnout risk; Priya: platform work slowing", "impact": "positive"},
            {"point": "CKA requirement reduces candidate pool unnecessarily", "evidence": "Ryan manages cluster successfully without CKA", "impact": "negative"},
        ],
    }, confidence=0.89)

    # Candidates
    res_dmitri = _doc(db, pid, "dmitri_volkov_resume.txt",
        "Dmitri Volkov — Platform Engineer\n5 years. Kubernetes, Terraform, ArgoCD, GitOps, Go, Helm, Prometheus, Grafana, Docker, Azure\nPrevious: IDP team at Booking.com (2 years), SRE at Deutsche Telekom (2 years)\nCKA certified",
        "resume",
        {"full_name": "Dmitri Volkov", "email": "dmitri.volkov@gmail.com", "years_of_experience": 5,
         "skills": ["Kubernetes", "Terraform", "ArgoCD", "GitOps", "Go", "Helm", "Prometheus", "Grafana", "Docker", "Azure"],
         "summary": "Platform engineer. IDP at Booking.com. CKA certified. Go developer."})

    res_alice = _doc(db, pid, "alice_morgan_resume.txt",
        "Alice Morgan — DevOps Engineer\n4 years. Jenkins, Docker, AWS, Ansible, Bash, Python\nPrevious: CI/CD pipelines at UK retail company\nNo Kubernetes operator experience, no Go.",
        "resume",
        {"full_name": "Alice Morgan", "email": "alice.morgan@outlook.com", "years_of_experience": 4,
         "skills": ["Jenkins", "Docker", "AWS", "Ansible", "Bash", "Python"],
         "summary": "Traditional DevOps. CI/CD and configuration management. No Kubernetes depth."})

    res_ben = _doc(db, pid, "ben_foster_resume.txt",
        "Ben Foster — Senior Platform/SRE Engineer\n7 years. Kubernetes (CKA+CKS), Go, Terraform, Helm, ArgoCD, Istio, Prometheus, Grafana, Kubernetes Operators (3 custom operators in production), Internal Developer Platform\nPrevious: Platform Engineering at Spotify (3 years), SRE at Cloudflare (2 years)\nPublic speaker at KubeCon 2023",
        "resume",
        {"full_name": "Ben Foster", "email": "ben.foster@fastmail.com", "years_of_experience": 7,
         "skills": ["Kubernetes", "Go", "Terraform", "Helm", "ArgoCD", "Istio", "Prometheus", "Grafana", "Kubernetes Operators", "IDP"],
         "work_history": [
             {"title": "Staff Platform Engineer", "company": "Spotify", "duration": "3 years", "description": "Built internal developer platform serving 500 engineers. 3 custom Kubernetes operators in production."},
             {"title": "Senior SRE", "company": "Cloudflare", "duration": "2 years", "description": "Multi-cluster Kubernetes, global edge infrastructure."},
         ],
         "summary": "KubeCon speaker. CKA+CKS. Kubernetes Operators expert. IDP at Spotify scale."})

    ar_D_dmitri = _analysis(db, pid, "D", [res_dmitri.id, jd5.id], {
        "overall_score": 82, "verdict": "moderate_fit",
        "skill_match": {"score": 85, "matched": ["Kubernetes", "Terraform", "ArgoCD", "Go", "Helm", "Prometheus", "Azure", "CKA"], "missing": ["Kubernetes Operators (unclear)", "IDP depth"], "notes": "Strong base match. Booking.com IDP experience is relevant."},
        "experience_match": {"score": 85, "relevant_years": 5, "notes": "5 years, Booking.com IDP and Deutsche Telekom SRE. Good progression."},
        "team_complementarity": {"score": 80, "fills_gaps": ["Go platform development", "IDP tooling", "Prometheus/Grafana observability"], "overlaps": ["Kubernetes (Ryan)", "Terraform (Ryan)", "ArgoCD (Ryan)"], "team_dynamics": "Would work closely with Ryan. Some overlap acceptable — adds Go and IDP depth.", "recommendation": "Solid candidate. Verify Kubernetes Operators experience depth."},
        "strengths": ["Booking.com IDP experience", "CKA certified", "Go + Kubernetes combination", "Azure matches client stack"],
        "gaps": ["Kubernetes Operators experience not explicit on resume", "IDP at smaller scale than Spotify"],
        "confidence": 0.82, "confidence_level": "HIGH",
        "confidence_explanation": "Good resume data, clear team context.", "sources": ["Dmitri's resume", "JD", "Team context"],
        "reasoning": "Dmitri is a strong candidate. His Booking.com IDP experience and CKA certification match well. Go skills fill the gap identified in Priya's report. Main uncertainty is depth of Kubernetes Operators experience.",
        "key_arguments": [
            {"point": "Booking.com IDP experience is relevant", "evidence": "JD requires IDP development; Booking.com is known for internal platform tooling", "impact": "positive"},
            {"point": "Azure stack alignment", "evidence": "Ryan uses Azure AKS; Dmitri lists Azure — no ramp-up needed", "impact": "positive"},
            {"point": "Operator experience unclear", "evidence": "Resume doesn't explicitly mention Kubernetes Operators", "impact": "negative"},
        ],
        "data_sources_used": ["resume", "jd"],
    }, confidence=0.82)

    ar_D_alice = _analysis(db, pid, "D", [res_alice.id, jd5.id], {
        "overall_score": 42, "verdict": "risky",
        "skill_match": {"score": 38, "matched": ["Docker", "Python", "CI/CD (Jenkins)"], "missing": ["Kubernetes", "Terraform", "Helm", "ArgoCD", "Go", "Platform engineering"], "notes": "Traditional DevOps profile. Missing all Kubernetes-native skills."},
        "experience_match": {"score": 55, "relevant_years": 2, "notes": "4 years DevOps but AWS/Jenkins, not Kubernetes-native. 2 years transferable."},
        "team_complementarity": {"score": 20, "fills_gaps": [], "overlaps": ["Docker (Ryan, Priya)", "Python (Priya)"], "team_dynamics": "Would not meaningfully relieve Ryan. Lacks the Kubernetes depth needed.", "recommendation": "High risk hire. Would require extensive Kubernetes upskilling on the job."},
        "strengths": ["CI/CD experience", "Python basics"],
        "gaps": ["No Kubernetes", "No Terraform", "No Go", "No ArgoCD", "Traditional DevOps, not platform engineering"],
        "confidence": 0.84, "confidence_level": "HIGH",
        "confidence_explanation": "Resume gap is clear.", "sources": ["Alice's resume", "JD"],
        "reasoning": "Alice is a traditional DevOps engineer with AWS/Jenkins experience. The role requires Kubernetes-native platform engineering. This would require 6+ months upskilling before she could contribute meaningfully.",
        "key_arguments": [
            {"point": "No Kubernetes experience", "evidence": "Resume: no Kubernetes mentioned — entire platform is K8s-native", "impact": "negative"},
            {"point": "Jenkins vs GitOps — different paradigm", "evidence": "JD requires ArgoCD/GitOps; Alice uses Jenkins", "impact": "negative"},
        ],
        "data_sources_used": ["resume", "jd"],
    }, confidence=0.84)

    ar_D_ben = _analysis(db, pid, "D", [res_ben.id, jd5.id], {
        "overall_score": 99, "verdict": "strong_fit",
        "skill_match": {"score": 100, "matched": ["Kubernetes", "Go", "Terraform", "Helm", "ArgoCD", "Istio", "Prometheus", "Grafana", "Kubernetes Operators", "IDP", "CKA+CKS"], "missing": [], "notes": "Perfect. Exceeds every requirement. KubeCon speaker."},
        "experience_match": {"score": 99, "relevant_years": 7, "notes": "7 years. Spotify IDP (500 engineers) + Cloudflare global Kubernetes. Top 1% profile."},
        "team_complementarity": {"score": 100, "fills_gaps": ["Kubernetes Operators", "Istio service mesh (matches Priya's prototype)", "IDP at scale", "Multi-cluster federation (Cloudflare)", "Advanced Go"], "overlaps": ["Kubernetes (Ryan — but Ben is at a higher level)", "ArgoCD (Ryan)"], "team_dynamics": "Would transform the team. Ryan can refocus on client ops; Ben drives platform development. Priya's service mesh work would directly benefit.", "recommendation": "Close offer immediately. This candidate will not stay on market long."},
        "strengths": ["KubeCon speaker — thought leader", "3 custom Kubernetes Operators in production at Spotify", "Spotify IDP serves 500 engineers — exceeds project scale", "Cloudflare multi-cluster experience"],
        "gaps": ["Rate expectations likely high (Spotify/Cloudflare background)"],
        "confidence": 0.99, "confidence_level": "HIGH",
        "confidence_explanation": "Exceptional resume, perfect team fit, zero ambiguity.",
        "sources": ["Ben's resume", "JD", "Team context (Ryan/Priya reports)"],
        "reasoning": "Ben is the ideal candidate. Spotify IDP and Cloudflare SRE experience exceeds every JD requirement. His 3 custom Kubernetes Operators directly address the team's primary gap. KubeCon speaker adds credibility.",
        "key_arguments": [
            {"point": "3 custom Kubernetes Operators in production", "evidence": "Spotify resume: 3 custom operators — exact gap on current team", "impact": "positive"},
            {"point": "Istio experience supports Priya's service mesh work", "evidence": "Priya W8: doing service mesh prototype; Ben has Istio production experience", "impact": "positive"},
            {"point": "Spotify IDP serves 500 engineers — scale exceeds project needs", "evidence": "Project requires IDP for single team; Ben has 500-engineer scale experience", "impact": "positive"},
            {"point": "Rate risk from Spotify/Cloudflare background", "evidence": "Top-tier companies — may expect $12k+/month", "impact": "negative"},
        ],
        "data_sources_used": ["resume", "jd", "reports"],
    }, confidence=0.99)

    _candidate(db, pos5.id, "Dmitri Volkov", "dmitri.volkov@gmail.com", "+49 170 333 4455", "Berlin, Germany", 5,
               "technical_interview", 82.0, "moderate_fit", ar_D_dmitri.id, res_dmitri.id,
               recruiter_notes="Good profile. Booking.com IDP relevant. Scheduled technical interview.",
               interview_notes="Kubernetes depth confirmed. Operators experience: 1 custom operator (unpublished). ArgoCD strong.",
               tags=["kubernetes", "argo", "go", "cka"],
               candidate_rate=8000.0)

    _candidate(db, pos5.id, "Alice Morgan", "alice.morgan@outlook.com", "+44 7700 900 123", "London, UK", 4,
               "screening", 42.0, "risky", ar_D_alice.id, res_alice.id,
               recruiter_notes="Traditional DevOps. Missing Kubernetes. May need significant ramp-up.",
               tags=["devops", "aws", "risk-profile"],
               candidate_rate=6500.0)

    _candidate(db, pos5.id, "Ben Foster", "ben.foster@fastmail.com", "+31 6 12 34 56 78", "Amsterdam, Netherlands", 7,
               "offer", 99.0, "strong_fit", ar_D_ben.id, res_ben.id,
               recruiter_notes="KubeCon speaker. Spotify+Cloudflare. Exceptional. Offer extended $11,000/month.",
               interview_notes="Technical: flawless. Live-coded a Kubernetes operator. Explained Istio mTLS architecture. Multi-cluster design impeccable.",
               client_feedback="Best candidate we've seen. Yes — close it.",
               tags=["kubernetes-operator", "spotify", "kubecon", "top-candidate"],
               candidate_rate=11000.0, availability="4 weeks notice")

    db.commit()
    print(f"Project 3 created: {p3.name} (id={pid}) | 2 team | 1 position (35d CRITICAL) | 3 candidates")

finally:
    db.close()

print("\n✅ Seed complete! 3 projects, 9 team members, 4 positions, 10 candidates.")
print("   All entities populated with realistic AI analysis results.")
