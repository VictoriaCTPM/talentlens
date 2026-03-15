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
