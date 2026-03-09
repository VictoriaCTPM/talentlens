# TalentLens — Project Tracking

## Phase 1: Research ✅ COMPLETE
- [x] Requirements gathered
- [x] Workflow mapped (JD → hire → reports)
- [x] Pain points identified (slow candidate search)
- [x] Data formats confirmed (PDF, DOC, DOCX, TXT)

## Phase 2: Planning ✅ COMPLETE
- [x] Architecture designed (3-layer: Memory, Brain, Face)
- [x] Tech stack selected (Groq + Railway + ChromaDB + sentence-transformers)
- [x] Document processing pipeline specified
- [x] AI analysis modes defined (A/B/C/D)
- [x] Anti-hallucination system designed (5 levels)
- [x] UI/UX design completed (Design.md)
- [x] LLM provider abstraction designed
- [x] Privacy review done — Groq safe for real data
- [x] 9-point architecture review completed
- [x] All documentation created

## Phase 3: Development 🔄 IN PROGRESS

### Etap 1: Backend Foundation & Document Ingestion
| # | Task | Status | Test |
|---|------|--------|------|
| 1.1 | Scaffold FastAPI project | ⬜ | Server starts at localhost:8000 |
| 1.2 | Config & settings (.env loader) | ⬜ | Settings load correctly |
| 1.3 | Database models (SQLAlchemy) | ⬜ | Tables created |
| 1.4 | Pydantic schemas | ⬜ | Validation works |
| 1.5 | LLM provider abstraction | ⬜ | Groq call returns response |
| 1.6 | Rate limiter | ⬜ | Limits enforced |
| 1.7 | Document parser (PDF + DOC) | ⬜ | Text extracted from test files |
| 1.8 | Document classifier + extractor | ⬜ | JSON structure returned |
| 1.9 | Local embeddings (sentence-transformers) | ⬜ | Vectors generated |
| 1.10 | ChromaDB vector store | ⬜ | Chunks stored and retrieved |
| 1.11 | Async job queue + SSE | ⬜ | Job status updates stream |
| 1.12 | API endpoints (projects, documents, jobs) | ⬜ | Full upload-to-processed flow |
| **TEST CHECKPOINT 1** | Upload a real document, see it processed | ⬜ | End-to-end works |

### Etap 2: Retrieval & Search
| # | Task | Status | Test |
|---|------|--------|------|
| 2.1 | BM25 keyword search | ⬜ | Relevant results returned |
| 2.2 | Vector similarity search | ⬜ | Semantic matches found |
| 2.3 | Hybrid search (RRF fusion) | ⬜ | Combined ranking works |
| 2.4 | Metadata filtering | ⬜ | Filters narrow results |
| **TEST CHECKPOINT 2** | Search finds relevant info from uploaded docs | ⬜ | |

### Etap 3: AI Analysis Engine
| # | Task | Status | Test |
|---|------|--------|------|
| 3.1 | Mode A — Talent Brief | ⬜ | JD → structured brief |
| 3.2 | Mode B — Historical Match | ⬜ | Similar positions found |
| 3.3 | Mode C — Level Advisor | ⬜ | Level recommendation + evidence |
| 3.4 | Mode D — Candidate Scorer | ⬜ | Score + breakdown + verdict |
| 3.5 | Data sufficiency checker | ⬜ | "Not enough data" warning works |
| **TEST CHECKPOINT 3** | All 4 modes produce quality output | ⬜ | |

### Etap 4: Frontend
| # | Task | Status | Test |
|---|------|--------|------|
| 4.1 | Next.js scaffold + shadcn/ui | ⬜ | App loads in browser |
| 4.2 | Dashboard (project cards + stats) | ⬜ | Projects displayed |
| 4.3 | Project detail (tabs) | ⬜ | Navigation works |
| 4.4 | Document upload + processing status | ⬜ | Upload → spinner → done |
| 4.5 | AI Analysis view (4 modes) | ⬜ | Structured cards render |
| 4.6 | Candidate ranking table | ⬜ | Sorted, clickable |
| 4.7 | Pipeline Monitor page | ⬜ | Table with aging alerts |
| **TEST CHECKPOINT 4** | Full flow in browser | ⬜ | |

### Etap 5: Polish & Deploy
| # | Task | Status | Test |
|---|------|--------|------|
| 5.1 | Error handling & edge cases | ⬜ | Graceful error messages |
| 5.2 | Loading states & empty states | ⬜ | No blank screens |
| 5.3 | Deploy backend to Railway | ⬜ | API accessible online |
| 5.4 | Deploy frontend to Vercel | ⬜ | App accessible online |
| 5.5 | Connect Railway PostgreSQL | ⬜ | Production DB works |
| 5.6 | End-to-end test on production | ⬜ | Full flow works online |
| **DELIVERY** | MVP ready for real use | ⬜ | |

## Phase 4: Polishing (post-MVP)
- [ ] Dark mode
- [ ] OneDrive integration
- [ ] PDF export of analyses
- [ ] Multi-candidate comparison view
- [ ] Automated weekly report generation
- [ ] Role-based access

## Phase 5: Delivery
- [ ] Documentation for end users
- [ ] Training session
- [ ] Improvement roadmap
