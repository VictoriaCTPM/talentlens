# TalentLens — Architecture Decisions

## DEC-001: LLM Provider — Groq Free Tier
- **Date**: 2026-03-06
- **Decision**: Use Groq (Llama 3.3 70B) as primary LLM
- **Rationale**: Free, fast (~200 tok/s), data NOT used for training (safe for real client data), 1000 RPD sufficient for MVP
- **Trade-offs**: 100K tokens/day limit, no native embeddings
- **Migration path**: Groq Developer tier ($0.27/M tokens) or Gemini Paid

## DEC-002: Local Embeddings — sentence-transformers
- **Date**: 2026-03-06
- **Decision**: Use all-MiniLM-L6-v2 locally instead of API-based embeddings
- **Rationale**: 100% free, data never leaves server, 384-dim vectors are sufficient for our corpus size, ~80MB model, runs on CPU
- **Trade-offs**: Slightly lower quality than large models; adequate for ~15-20 projects
- **Migration path**: Switch to API embeddings if quality insufficient

## DEC-003: Storage — Railway (PostgreSQL + Volume + ChromaDB)
- **Date**: 2026-03-06
- **Decision**: Host everything on Railway — backend, DB, files, vectors
- **Rationale**: Single platform, simple deployment via GitHub, persistent volumes available, PostgreSQL included, $5/mo after trial
- **Trade-offs**: $5/mo cost, Railway volume doesn't have built-in backup
- **Migration path**: Move to AWS/GCP if scaling needed

## DEC-004: Local dev uses SQLite, production uses PostgreSQL
- **Date**: 2026-03-06
- **Decision**: SQLAlchemy abstracts DB; use SQLite for development, PostgreSQL for Railway
- **Rationale**: Zero-setup local dev, no need to run Postgres locally
- **Switch**: Change DATABASE_URL in .env

## DEC-005: Document chunking — type-specific strategy
- **Date**: 2026-03-06
- **Decision**: Each doc type has its own chunking logic
- **Rules**:
  - Resume → chunk by section (Education, Experience, Skills)
  - JD → single chunk (usually short enough)
  - Weekly Report → chunk by developer/section
  - Interview Notes → single chunk
  - Client Report → chunk by section
- **Rationale**: Prevents mixing unrelated info in one chunk

## DEC-006: Hybrid search — BM25 + Vector + RRF
- **Date**: 2026-03-06
- **Decision**: Use both keyword (BM25) and semantic (vector) search, merge with Reciprocal Rank Fusion
- **Rationale**: Keywords catch exact matches (names, techs), vectors catch meaning
- **No LLM reranker** on free tier to save API calls

## DEC-007: Batch LLM calls — classify + extract in 1 request
- **Date**: 2026-03-06
- **Decision**: Combine document classification and structured extraction into a single LLM call
- **Rationale**: Reduces API calls from 3→1 per document, critical for free tier limits

## DEC-008: Anti-hallucination — 5-level system
- **Date**: 2026-03-06
- **Decision**: Implement grounding prompts, citations, Pydantic validation, cross-check, confidence scoring
- **Rationale**: Trust is everything for a hiring tool; managers must trust AI output

## DEC-009: Async job queue — not Celery, just asyncio
- **Date**: 2026-03-06
- **Decision**: Use Python asyncio.Queue + SQLite/PostgreSQL job table instead of Celery/Redis
- **Rationale**: Simpler infrastructure, no Redis needed, sufficient for 2-3 concurrent users
- **Migration path**: Add Celery + Redis if scaling beyond 10 concurrent users

## DEC-010: UI Design — "Structured Intelligence" pattern
- **Date**: 2026-03-09
- **Decision**: AI results shown as structured cards, not chat text
- **Key patterns**: Mode badges (A/B/C/D), confidence bars, source citations, skill/gap chips, score breakdowns
- **Rationale**: Builds trust; feels systematic; scannable for busy managers
- **Component library**: shadcn/ui (accessible, customizable, Tailwind-based)

## DEC-011: No Sidebar — top nav only
- **Date**: 2026-03-09
- **Decision**: Fixed top navigation bar, no sidebar
- **Rationale**: Only 2 primary nav items (Dashboard, Pipeline); maximize content width for data-dense views

## DEC-012: LLM Provider Abstraction
- **Date**: 2026-03-09
- **Decision**: Abstract LLM client with `generate()` and `embed()` methods; switch via `LLM_PROVIDER` env var
- **Rationale**: Easy to switch between Groq/Gemini/future providers without changing application code

## DEC-013: Privacy Tiers
- **Date**: 2026-03-09
- **Decision**: Groq free tier is safe for real data (confirmed: data NOT used for training)
- **Additional safety**: local embeddings, Railway encrypted storage

## DEC-014: Deployment Platform
- **Date**: 2026-03-09
- **Decision**: Railway for backend + DB + ChromaDB; Vercel for frontend
- **Cost**: ~$5-10/mo after Railway trial
## DEC-015: NumPy version pinning for ChromaDB
- **Date**: 2026-03-09
- **Decision**: Use `.venv` virtualenv with pinned NumPy < 2.0 for local backend dev
- **Rationale**: ChromaDB uses `np.float_` removed in NumPy 2.0; system Python has NumPy 2.x
- **Fix**: Always start backend with `source .venv/bin/activate && uvicorn ...`
- **Migration path**: Upgrade ChromaDB when they release NumPy 2.0 compatible version

## DEC-016: CandidateEvent timeline pattern
- **Date**: 2026-03-09
- **Decision**: Log all candidate lifecycle changes to `candidate_events` table (event_type + JSON event_data)
- **Event types**: `created`, `status_change`, `scored`
- **Rationale**: Provides full audit trail for recruiters; enables timeline UI without additional complexity
- **Trade-offs**: Slightly more writes per operation; negligible at current scale

## DEC-017: Explicit Position and Candidate entities
- **Date**: 2026-03-09
- **Decision**: Add Position (from JD) and Candidate (resume + status) as first-class DB entities
- **Rationale**: Without these, the app can't track hiring pipeline, candidate status,
  or generate dashboard metrics. Documents alone are not enough — a candidate has a
  lifecycle (new → screening → interview → hired/rejected) tied to a specific position.
- **Impact**: New DB models, new API endpoints, updated frontend tabs, Pipeline Monitor
  now reads real data instead of mock data
- **Status**: Approved

## DEC-018: AnalysisEngine uses internal SessionLocal, not injected db
- **Date**: 2026-03-09
- **Decision**: `AnalysisEngine` opens its own `SessionLocal()` sessions internally; callers must NOT pass `db` to constructor
- **Rationale**: Engine is a service layer, not a FastAPI dependency; it manages its own DB lifecycle
- **API callers**: Use `get_analysis_engine()` factory, not `AnalysisEngine(db)`
- **Result shape**: `engine.candidate_score()` returns plain `dict` (not ORM object); `result_id` key holds saved AnalysisResult ID

## DEC-019: Candidate Profile page (/candidates/[id])
- **Date**: 2026-03-09
- **Decision**: Dedicated candidate profile page with inline-editable fields (click-to-edit pattern)
- **Layout**: 60/40 two-column — left: AI scores + profile fields; right: recruiter/interview/client notes
- **Pattern**: Each field shows value or placeholder; click → input; blur → auto-save via PATCH
- **Rationale**: Eliminates modal overload; faster editing flow for recruiters

## DEC-020: Document upload with preset doc_type
- **Date**: 2026-03-09
- **Decision**: `POST /api/projects/{id}/documents` accepts optional `doc_type` form field
- **Valid values**: `jd`, `resume`, `report`, `interview`, `other`
- **Rationale**: When uploading from categorized UI sections, classification LLM call is redundant; preset saves API quota
- **Fallback**: If `doc_type` not provided or invalid, normal LLM classification runs

## DEC-021: Mode E — JD Reality Check analysis mode
- **Date**: 2026-03-11
- **Decision**: Add Mode E that audits a JD against current team + weekly reports
- **Output**: `skills_vs_reality` (JD requirements vs team's actual skills), `workload_analysis` (JD claims vs report reality), `necessity_check` (is this hire justified?), `jd_improvement_suggestions`
- **Sufficiency**: Only requires 1 JD to run; team/reports availability affects quality rating (low/medium/high) but does not block execution
- **Endpoint**: `POST /api/analysis/jd-reality-check`
- **Rationale**: Prevents redundant hires; exposes JD inaccuracies before wasting recruiter time

## DEC-022: Mode A — team-aware skill criticality
- **Date**: 2026-03-11
- **Decision**: Mode A prompt now classifies skill criticality based on current team: skills already covered by existing members → `"nice"`, skills genuinely missing from the team → `"must"`
- **Rationale**: Without team context, all skills default to must-have which wastes search effort. Team-aware criticality focuses recruiters on real gaps.
- **Dependency**: Requires `TeamContextService.get_team_context(project_id)` to return populated team data

## DEC-023: Mode D — team_complementarity as scored dimension
- **Date**: 2026-03-11
- **Decision**: Add `team_complementarity` as a fifth scoring dimension in Mode D (Candidate Scorer)
- **Fields**: `score` (0-100), `fills_gaps` (skills candidate brings that team lacks), `overlaps` (skills candidate has that team already has), `team_dynamics` (seniority fit), `recommendation` (specific team-fit advice)
- **Score impact**: Candidate filling genuine team gaps → boost overall_score; candidate only duplicating existing skills → lower overall_score
- **Fallback**: If no team data available, `score=50`, fills_gaps=[], overlaps=[], team_dynamics="No team data available"

## DEC-024: Auto-link reports to team members after processing
- **Date**: 2026-03-11
- **Decision**: After a report/interview document is processed (step 9 in job_queue.py), attempt fuzzy name match between `extracted_data.developer_name` and `TeamMember.name` to set `document.team_member_id`
- **Match logic**: `try_link_report_to_team_member()` in `api/team.py`; wrapped in try/except so failure never blocks processing
- **Frontend**: Documents tab shows green "→ Linked to: Name" for linked reports, amber warning with hint name for unlinked; manual link dropdown available

## DEC-025: developer_name_hint in document list response
- **Date**: 2026-03-11
- **Decision**: `GET /api/projects/{id}/documents` batch-loads `ExtractedData` for report/interview docs in a single IN query and returns `developer_name_hint` field
- **Pattern**: Single extra query (not N+1); used by frontend to show "this report mentions John Smith — link?" prompt
- **Fields added to DocumentResponse**: `team_member_id: Optional[int]`, `developer_name_hint: Optional[str]`

## DEC-026: Mode D — Structured Scoring Formula (7-step, role alignment gate)
- **Date**: 2026-03-15
- **Decision**: Replace impression-based Mode D candidate scoring with a deterministic 7-step weighted formula
- **Steps**:
  1. Role Alignment Gate — detect engineer vs manager mismatch; if mismatch → cap score ≤ 35, force `not_recommended`
  2. Hard Skills (40%) — `hands_on` = 1.0, `exposure` = 0.2, `none` = 0.0; scored per must-have skill
  3. Experience (25%) — years comparison + role type match
  4. Domain (15%) — industry alignment + relevant knowledge
  5. Soft Skills (10%) — communication + collaboration + problem_solving sub-scores
  6. Team Fit (10%) — compatibility + complementarity (fills_gaps vs overlaps)
  7. Math — weighted sum → `score_breakdown` with `role_cap_applied` flag
- **New Pydantic schemas**: `RoleAlignment`, `MustHaveSkillMatch`, `DomainMatch`, `SoftSkillsBreakdown`, `ScoreBreakdown`; updated `SkillMatchDetail`, `ExperienceMatch`, `CandidateScoreResult`, `BatchCandidateScoreItem`
- **Fail-safe**: `RoleAlignment` defaults to `role_alignment_score=10` — any incomplete LLM response is treated as a mismatch (score capped at 35)
- **Validator**: Two-phase `@model_validator(mode="after")` — role gate first, then standard threshold check (85/65/45)
- **Rationale**: Reproducible, auditable scoring; eliminates prompt-level variability; enables score_breakdown UI card

## DEC-027: E2E test suite — pytest with mocked services
- **Date**: 2026-03-15
- **Decision**: Add `backend/tests/test_e2e.py` (50 ordered tests) + `backend/tests/conftest.py` (session fixtures)
- **Mock strategy**:
  - `MockLLM` — deterministic JSON dispatch by prompt content markers; no Groq API calls
  - `MockEmbeddingService` — returns 384-dim zero vectors; no model download
  - `MockVectorStore` — no-op stubs; no ChromaDB disk I/O
  - Separate SQLite DB (`data/test_e2e.db`), wiped before and after each session
- **Coverage**: health → projects → positions → documents (async processing) → JD attachment → team → analysis (5 modes) → candidates → batch scoring → search → pipeline monitor → delete cleanup
- **Runtime**: ~1.15s for 50 tests
- **Rationale**: Fast, deterministic CI without external dependencies; catches regressions across all API contracts
