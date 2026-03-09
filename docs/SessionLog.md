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

## Session 2 (Phase 3: Development begins)
- [ ] Setup environment
- [ ] Start Etap 1
