# TalentLens — Claude.md (Master Project Document)

## Project Identity
- **Name**: TalentLens
- **Type**: AI-powered Talent Intelligence Platform
- **Purpose**: Analyze historical project data to provide hiring recommendations
- **Tagline**: "AI that hires like your best manager — because it remembers everything"

## Tech Stack
| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | Python 3.11+ / FastAPI | Async, fast, auto-generates API docs |
| Frontend | Next.js 14 / React / Tailwind / shadcn/ui | Modern, fast, component library |
| Primary LLM | Groq (Llama 3.3 70B) — free tier | Fast inference, data NOT used for training |
| Fallback LLM | Gemini Paid (when needed) | Broader context window |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) — local | Free, private, no API calls |
| Vector DB | ChromaDB (on Railway volume) | Lightweight, Python-native |
| Database | PostgreSQL (Railway) / SQLite (local dev) | Structured data storage |
| File Storage | Railway Volume / local `data/uploads/` | Persistent file storage |
| Hosting Backend | Railway ($5/mo after trial) | Simple Python deployment |
| Hosting Frontend | Vercel (free) | Optimized for Next.js |

## LLM Provider Abstraction
All LLM calls go through `backend/app/services/llm/base.py`.
Switch providers by changing `LLM_PROVIDER` in `.env`:
- `groq_free` — Llama 3.3 70B via Groq (default)
- `gemini_paid` — Gemini 2.5 Flash via Google AI
- `groq_dev` — Groq Developer tier (higher limits)

## Rate Limits (Groq Free — llama-3.3-70b-versatile)
- 30 RPM (requests per minute)
- 1,000 RPD (requests per day)
- 12,000 TPM (tokens per minute)
- 100,000 TPD (tokens per day)
Optimization: batch classification + extraction into 1 call, cache everything.

## Project Structure
Copy
talentlens/ ├── backend/ │ ├── app/ │ │ ├── init.py │ │ ├── main.py # FastAPI app entry point │ │ ├── config/ │ │ │ ├── init.py │ │ │ └── settings.py # Pydantic Settings (.env loader) │ │ ├── models/ │ │ │ ├── init.py │ │ │ └── database.py # SQLAlchemy models │ │ ├── schemas/ │ │ │ ├── init.py │ │ │ └── schemas.py # Pydantic request/response schemas │ │ ├── services/ │ │ │ ├── init.py │ │ │ ├── llm/ │ │ │ │ ├── init.py │ │ │ │ ├── base.py # Abstract LLM client │ │ │ │ ├── groq_provider.py │ │ │ │ └── gemini_provider.py │ │ │ ├── document_parser.py # PDF/DOC text extraction │ │ │ ├── document_processor.py # Classify + extract + embed │ │ │ ├── embeddings.py # Local sentence-transformers │ │ │ ├── vector_store.py # ChromaDB operations │ │ │ ├── retrieval.py # BM25 + vector hybrid search │ │ │ ├── analysis.py # AI analysis modes A/B/C/D │ │ │ └── job_queue.py # Async processing queue │ │ ├── api/ │ │ │ ├── init.py │ │ │ ├── projects.py # /api/projects CRUD │ │ │ ├── documents.py # /api/documents upload + status │ │ │ ├── analysis.py # /api/analysis trigger + results │ │ │ └── jobs.py # /api/jobs status + SSE stream │ │ └── utils/ │ │ ├── init.py │ │ └── rate_limiter.py # Token-bucket rate limiter │ ├── requirements.txt │ ├── Dockerfile │ └── alembic/ # DB migrations (created later) ├── frontend/ │ ├── src/ │ │ ├── app/ # Next.js app router pages │ │ ├── components/ # React components │ │ ├── lib/ # API client, utilities │ │ └── hooks/ # React hooks │ ├── package.json │ ├── tailwind.config.js │ └── Dockerfile ├── data/ │ ├── uploads/ # Uploaded files (gitignored) │ └── chroma/ # ChromaDB data (gitignored) ├── docs/ │ ├── Claude.md # THIS FILE │ ├── ProjectTracking.md # Phase/task tracking │ ├── SessionLog.md # What happened each session │ ├── NextSession.md # What to do next │ ├── Decisions.md # Architecture decisions │ └── Design.md # UI/UX specification ├── .env # Secret keys (gitignored) ├── .gitignore ├── docker-compose.yml └── README.md


## Document Processing Pipeline
Upload file → Save to disk/volume → Parse (PyMuPDF for PDF, python-docx for DOC/DOCX) → Classify document type via LLM (JD / Resume / Report / Interview / JobRequest / ClientReport) → Extract structured data via LLM into Pydantic schemas → Store structured data in PostgreSQL → Chunk text (strategy depends on doc type) → Generate embeddings locally (sentence-transformers) → Store chunks + embeddings in ChromaDB with rich metadata → Mark document as processed


## AI Analysis Modes
- **Mode A — Talent Brief**: JD → skill checklist, search tips, pitfalls, historical context; team context adjusts skill criticality (team-covered skills = "nice", gaps = "must")
- **Mode B — Historical Match**: JD → similar past positions, success/failure patterns
- **Mode C — Level Advisor**: JD → recommended seniority with evidence from past projects; considers existing team level distribution
- **Mode D — Candidate Scorer**: Resume + JD → score 0-100, skill/experience/team match, verdict; includes `team_complementarity` (fills_gaps, overlaps, team_dynamics, recommendation)
- **Mode E — JD Reality Check**: JD + team resumes + weekly reports → audit whether JD matches project reality, skills_vs_reality table, workload_analysis, necessity_check, jd_improvement_suggestions
- **Team Context**: All modes (A, B, C, D, E) receive current team composition (`TeamContextService.get_team_context()`) as additional prompt context for smarter, team-aware recommendations

## Anti-Hallucination System (5 levels)
1. Grounding prompt: "Answer ONLY based on provided documents"
2. Mandatory citations: every claim cites source document
3. Pydantic validation: structured output, not free text
4. Cross-check: verify extracted facts against database
5. Confidence scoring: LOW/MEDIUM/HIGH with explanation

## Retrieval Strategy
- BM25 keyword search + vector cosine similarity
- Reciprocal Rank Fusion (RRF) to merge results
- Metadata pre-filters (project, date, doc type, person)
- No LLM reranker on free tier (add later for paid)

## Slash Commands (for keeping docs in sync)
- `/update-tracking` — update ProjectTracking.md
- `/update-session` — update SessionLog.md
- `/update-next` — update NextSession.md
- `/update-decisions` — update Decisions.md
- `/done` — update all of the above

## Privacy Rules
- Groq free tier: data NOT used for training (confirmed in ToS)
- Embeddings: generated locally, never leave the server
- Files: stored on Railway volume (encrypted at rest)
- Database: Railway PostgreSQL (encrypted)
- Real client data is acceptable with current architecture