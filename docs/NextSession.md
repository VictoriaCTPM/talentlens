# TalentLens — Next Session Plan

## Pre-check
Before starting, confirm:
1. [ ] VS Code open with talentlens folder
2. [ ] Claude Code extension works
3. [ ] Terminal: `python --version` shows 3.11+
4. [ ] Terminal: `node --version` shows 24+
5. [ ] Terminal: `git --version` works
6. [ ] `.env` file has GROQ_API_KEY filled in
7. [ ] GitHub repo created and code pushed

## Session Goal: Etap 1 — Backend Foundation & Document Ingestion

### Step-by-step plan:
1. **Scaffold FastAPI** — create main.py, requirements.txt, basic server
   → TEST: `python -m uvicorn backend.app.main:app --reload` → browser shows "TalentLens API"

2. **Config & Settings** — .env loader, settings.py
   → TEST: print settings in terminal, see Groq key loaded

3. **Database models** — SQLAlchemy models for Project, Document, ExtractedData, AnalysisResult, ProcessingJob, AICallLog
   → TEST: tables auto-created in SQLite

4. **Pydantic schemas** — request/response models for API + extracted document schemas
   → TEST: import works, validation catches bad data

5. **LLM provider abstraction** — base.py + groq_provider.py with rate limiting
   → TEST: send "Hello, respond with 'OK'" → get "OK" back

6. **Document parser** — PyMuPDF + python-docx → raw text
   → TEST: parse a real PDF/DOC → see text output

7. **Document processor** — classify + extract structured data via LLM
   → TEST: feed a real resume → get JSON with name, skills, experience

8. **Local embeddings** — sentence-transformers all-MiniLM-L6-v2
   → TEST: embed a sentence → get 384-dim vector

9. **ChromaDB vector store** — store and query chunks
   → TEST: store 3 chunks → query → get relevant one back

10. **Async job queue + SSE** — background processing with status stream
    → TEST: upload triggers async job → SSE sends status updates

11. **API endpoints** — projects CRUD + document upload + job status
    → TEST: full flow via FastAPI docs (localhost:8000/docs)

12. **END-TO-END TEST**: upload a real resume PDF → see it classified, extracted, embedded, stored, queryable
