# TalentLens — Session Log

## Session 1 (Phase 1-2: Research & Planning)
- Gathered requirements: AI analytics tool for consulting firm
- Mapped full hiring workflow (JD → hire → weekly reports)
- Identified main pain: slow candidate search, wasted resources
- Defined 6 document types: JD, Resume, WeeklyReport, InterviewNotes, JobRequest, ClientReport
- Designed 4 AI analysis modes (A/B/C/D)
- Selected tech stack: Python FastAPI + Next.js + Groq + ChromaDB
- Chose Groq over Gemini for data privacy (real client data)
- Designed document processing pipeline with Pydantic extraction
- Designed 5-level anti-hallucination system
- Chose local embeddings (sentence-transformers) for privacy
- Chose Railway for backend hosting, Vercel for frontend
- Designed LLM provider abstraction for easy switching
- Completed 9-point architecture review
- Completed UI/UX design via Lovable AI
- Created all project documentation

## Session 2 (Phase 3: Development begins — Etap 1 complete)
- [x] Scaffolded FastAPI backend (main.py, CORS, /health, settings.py)
- [x] SQLAlchemy models: Project, Document, ProcessingJob, ExtractedData, AnalysisResult
- [x] Pydantic schemas for all models
- [x] LLM provider abstraction (Groq + Gemini providers, base interface)
- [x] Document parser: PDF (PyMuPDF) + DOC/DOCX (python-docx)
- [x] Document processor: classify + extract in 1 LLM call (DEC-007)
- [x] Local embeddings via sentence-transformers (all-MiniLM-L6-v2)
- [x] ChromaDB vector store with project + doc_type metadata
- [x] Async job queue (asyncio.Queue, SSE streaming)
- [x] API: /projects, /documents, /jobs
- [x] Next.js frontend scaffold + shadcn/ui
- [x] Dashboard with project cards + stats
- [x] Project Detail: Positions tab, Documents tab, AI Analysis tab, Timeline tab
- [x] Document upload UI with processing status polling
- [x] Position model + API (CRUD, JD linking, days_open, candidates_count)
- [x] Candidate model + API (CRUD, AI scoring, status pipeline)
- [x] AI analysis modes A/B/C/D implemented in analysis.py
- [x] Pipeline Monitor page reading real data
- [x] Full upload-to-processed flow working end-to-end

## Session 3 (Phase 3: UI Polish — JD Upload + Candidate Profile)
- [x] JD upload flow in Position Detail (file upload + processing spinner + summary card)
- [x] ReplaceJdDialog for swapping JD on existing positions
- [x] JdSection component with status-based rendering
- [x] Fixed 422 errors on Score All (unprocessed resume guard + error display in row)
- [x] Fix 1: Removed Candidates tab from Project Detail; tab order = Positions | Documents | AI Analysis | Timeline
- [x] Fix 2: Enriched Candidate table — columns: # | Name | Score | Verdict | Skills Match | Experience | Status | Analyzed | Actions | expand
  - Name links to /candidates/[id]
  - Score circle, verdict badge, skills match mini progress bar, experience in years
  - Re-analyze button (RotateCcw) per row, expand row for breakdown
- [x] Fix 3: Replaced "Score All" button with blue info banner "💡 N candidates have not been analyzed yet" + "Analyze N Candidates" CTA
- [x] Fix 4: Redesigned Documents tab with categorized upload sections (JD / Resume / Report / Interview Notes / Other), each with description and per-category upload button
- [x] Fix 1 Addition: Candidate Profile page (/candidates/[id]) — two-column layout (60/40)
  - Left: AI score ring, breakdown (skills match bar, verdict), editable profile grid (10 fields), tag editor
  - Right: Recruiter notes, Interview notes, Client feedback, Rejection reason (conditional)
  - Activity Timeline at bottom
- [x] Extended Candidate model: 13 new columns (phone, current_company, current_role, years_of_experience, salary_expectation, location, availability, source, recruiter_notes, interview_notes, client_feedback, rejection_reason, tags JSON)
- [x] New CandidateEvent model for timeline (created, status_change, scored)
- [x] Extended Pydantic schemas: CandidateUpdate, CandidateResponse, CandidateEventResponse
- [x] GET /api/candidates/{id}/timeline endpoint
- [x] Auto-populate candidate profile from resume ExtractedData on creation
- [x] Backend: doc_type param on upload (pre-sets classification, skips LLM classify step)
- [x] Fixed AnalysisEngine(db) bug → get_analysis_engine() (was passing Session instead of LLM client)
- [x] Fixed result.result_data → result.get() (engine returns plain dict, not ORM object)
- [x] Created Textarea UI component (was missing from shadcn/ui setup)
- [x] SQLite ALTER TABLE migration for all new Candidate columns

## Session 4 (Phase 3: Scoring Formula Overhaul + E2E Test Suite)

### Mode D — Structured Scoring Formula (commit `4376cc0`)
- [x] Replaced impression-based Mode D scoring with deterministic 7-step weighted formula (DEC-026)
- [x] Step 1: Role Alignment Gate — engineer vs manager detection; mismatch caps score ≤ 35, forces `not_recommended`
- [x] Steps 2–6: Hard Skills 40%, Experience 25%, Domain 15%, Soft Skills 10%, Team Fit 10%
- [x] Step 7: Math — `score_breakdown` with `role_cap_applied` flag
- [x] New Pydantic schemas: `RoleAlignment`, `MustHaveSkillMatch`, `DomainMatch`, `SoftSkillsBreakdown`, `ScoreBreakdown`
- [x] Updated `SkillMatchDetail` (added `must_have_skills: list[MustHaveSkillMatch]`)
- [x] Updated `ExperienceMatch` (added `required_years`, `role_type_match`)
- [x] Updated `CandidateScoreResult` + `BatchCandidateScoreItem` with all new fields
- [x] Two-phase `@model_validator(mode="after")`: role gate → standard thresholds (85/65/45)
- [x] Fail-safe: default `role_alignment_score=10` → treats any incomplete LLM response as role mismatch
- [x] Updated Mode D prompt: "STRICT STRUCTURED FORMULA" with STEP 1–7 explicit instructions
- [x] Updated batch scoring prompt with same role gate logic

### E2E Test Suite + Data Wipe (commit `15359b1`)
- [x] Wiped all test data from `backend/data/talentlens.db` (22 projects, 38 docs, 15 candidates, 58 team members, 37 analysis results, etc.)
- [x] Cleared all files from `backend/data/uploads/`
- [x] Created `backend/tests/__init__.py`, `backend/tests/conftest.py`, `backend/tests/test_e2e.py`
- [x] `conftest.py`: session-scoped MockLLM (prompt-content dispatch), MockEmbeddingService (zero vectors), MockVectorStore (no-ops), separate test SQLite DB
- [x] `test_e2e.py`: 50 ordered tests covering full lifecycle — health → projects → positions → documents (async wait) → JD attachment → team → analysis (5 modes) → candidates → batch scoring → search → pipeline monitor → delete cleanup
- [x] Fixed: positions/team/JD attachment use `data=` (Form), not `json=`; list responses use `body["items"]`; search `project_id` as string; project delete requires manual TeamMember hard-delete (soft-delete rows cause NOT NULL violation on cascade)
- [x] Result: **50 passed, 1 warning in 1.15s**
