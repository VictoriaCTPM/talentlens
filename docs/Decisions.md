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
