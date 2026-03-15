# TalentLens Dead Code Audit
Generated: 2026-03-15
Scanned: `backend/app/` and `frontend/src/`

---

## Summary

| Category | Count |
|---|---|
| Unused imports found | 4 |
| Possibly unused functions | 3 |
| Possibly dead endpoints | 3 |
| Orphan components | 2 |
| Stale schema fields | 4 |
| Duplicate code blocks | 1 |
| Possibly unused DB columns | 1 |

---

## Recommended Actions (sorted by safety)

### Safe to Remove (zero references confirmed)

1. **`timezone` import in `database.py`** — imported on line 1 (`from datetime import datetime, timezone`) but `timezone` is never referenced in the file; only `datetime.utcnow` is used throughout.
2. **`TYPE_CHECKING` import in `embeddings.py`** — imported on line 6 (`from typing import TYPE_CHECKING`) but never used; there are no `if TYPE_CHECKING:` blocks in the file.
3. **`func` import in `team.py`** — `from sqlalchemy import func` on line 12 is never referenced; no `func.count` or similar calls exist in `team.py`. (Contrast: `func` is used in `projects.py` and `positions.py`.)
4. **`search` export in `frontend/src/lib/api.ts`** — The `search()` function (lines 316–333) wraps `POST /api/search`. It is never imported in any page or component. The local search filter in `projects/[id]/page.tsx` is a `useState("")` string filter — not this function.
5. **`getProjectCandidates` export in `frontend/src/lib/api.ts`** — Defined on line 406. Never imported in any frontend page or component. The endpoint `GET /api/projects/{project_id}/candidates` therefore has zero frontend callers.
6. **`VectorStore.count()` method** — The public `count()` method (line 144 of `vector_store.py`) is never called from outside `vector_store.py`. The internal `_collection.count()` call on line 33 (used in the constructor log message) is separate. No consumer in `backend/app/` ever calls `vs.count()`.
7. **`CandidateResponse.tags` field — not displayed in frontend** — The `tags` field is set in `CandidateUpdate`, stored in the DB, and returned in `CandidateResponse`, but no frontend page renders `candidate.tags`. It exists entirely on the backend with no UI surface.

### Probably Safe (used only in dead-end paths)

1. **`/api/analysis/position-intelligence` endpoint** — Defined in `analysis.py` lines 125–139. Neither `frontend/src/lib/api.ts` nor any frontend page imports or calls this endpoint. The frontend calls A/B/C modes individually via `runTalentBrief`, `runHistoricalMatch`, `runLevelAdvisor`. The endpoint and its backing `AnalysisEngine.position_intelligence()` method are unreachable from the UI.
2. **`/api/projects/{project_id}/team/overview` endpoint** — Defined in `team.py` line 214. Not referenced in `frontend/src/lib/api.ts` and not called from any frontend page. The overview data is returned inline inside `GET /api/projects/{project_id}/team` (as part of `TeamMemberList.overview`), making this standalone endpoint redundant.
3. **`/api/search` endpoint (POST)** — Defined in `search.py`. The `search()` function in `api.ts` wraps it but is never imported by any page. No frontend UI for hybrid search exists.

### Needs Human Decision

1. **`salary_expectation` field in frontend `Candidate` interface and `updateCandidate`** — The field `salary_expectation` appears in `frontend/src/lib/api.ts` (lines 58, 441) and is rendered/saved in `candidates/[id]/page.tsx` (lines 626–628). However, there is no corresponding column in `Candidate` DB model (`database.py`), no field in `CandidateResponse` schema, and no field in `CandidateUpdate`. This field is sent to the backend but silently dropped. Decision needed: add the backend field, or remove from frontend.
2. **`AICallLog` table** — Written to by `groq_provider.py` but never read by any endpoint, service, or page. There is no API to expose this data. The table is a pure write-only audit log. Decision needed: expose via an admin endpoint, or document as intentional observability-only storage.
3. **`avg_days_open` in `ProjectResponse`** — Computed and returned by the backend (`projects.py` lines 39–40), present in `frontend/src/lib/api.ts` as an interface field (line 16), but never rendered in any frontend page. The frontend shows `open_positions_count`, `health_status`, and `total_candidates_count` from the same response, but not `avg_days_open`. Decision needed: display it or remove from both backend and schema.
4. **`TeamMemberResponse.resume_summary`** — Populated by `team.py`'s `_member_to_response()` (pulls ExtractedData), present in `frontend/src/lib/api.ts` (line 99), but never read in any frontend page. `team/[id]/page.tsx` shows skills and recent reports but does not access `resume_summary`. Decision needed: use in team member detail page or remove from both.
5. **`_get_cached_mode_result` method in `AnalysisEngine`** — Defined at line 566 of `analysis.py`. Used internally by `position_intelligence()` only, which itself is unreachable from the frontend (see Scan 3). Decision needed: remove along with `position_intelligence`, or expose endpoint to UI.
6. **`Document.content_hash` exposed in `DocumentResponse`** — The `content_hash` (SHA-256) field is included in the `DocumentResponse` schema and in `frontend/src/lib/api.ts` (line 126). No frontend page renders or uses it — it is a backend-only deduplication mechanism. Decision needed: remove from public API response (it leaks file fingerprints), or keep as debugging aid.

---

## Detailed Reports

### Scan 1 — Unused Python Imports

| File | Import | Referenced in file? | Verdict |
|---|---|---|---|
| `backend/app/models/database.py` | `timezone` (from `datetime`) | No — only `datetime.utcnow` used | **UNUSED** |
| `backend/app/services/embeddings.py` | `TYPE_CHECKING` (from `typing`) | No — no `if TYPE_CHECKING:` block | **UNUSED** |
| `backend/app/api/team.py` | `func` (from `sqlalchemy`) | No — no `func.` call in file body | **UNUSED** |
| `backend/app/api/analysis.py` | `Optional` (from `typing`) | No — not referenced in this file | Checked: `Optional` is NOT present in analysis.py imports; imports are `Any, Optional` — verify: only `Any` is used in return types. `Optional` is not needed since Python 3.10+ union syntax is used elsewhere. |
| `backend/app/api/documents.py` | `Path` (from `pathlib`) | Yes — used in `_ext()` and `upload_dir` construction | USED — not an issue |
| `backend/app/api/candidates.py` | All imports | All used | OK |
| `backend/app/api/positions.py` | `Optional` | Yes — used at lines 47, 168, 170 | USED |
| `backend/app/services/analysis.py` | All 5 imports (`json`, `logging`, `datetime`, `timedelta`, `Any`, `BaseModel`, `ValidationError`, `model_validator`, `context_cache`, `LLMProvider`, `RetrievalService`, `TeamContextService`) | All used | OK |

> Note on `analysis.py` `Optional` import check: `analysis.py` imports `from typing import Any` only (line 8) — `Optional` is not imported there; it is imported in `positions.py` and `team.py`.

**Confirmed unused imports: 3** (`timezone` in database.py, `TYPE_CHECKING` in embeddings.py, `func` in team.py)

---

### Scan 2 — Possibly Unused Functions and Methods

| Function / Method | Defined in | Called from | Verdict |
|---|---|---|---|
| `VectorStore.count()` | `vector_store.py:144` | Nowhere outside `vector_store.py` | **POSSIBLY UNUSED** |
| `AnalysisEngine.position_intelligence()` | `analysis.py:453` | Only from `analysis.py:_run_position_intelligence` and `api/analysis.py` endpoint — but endpoint has no frontend caller | **EFFECTIVELY DEAD** (endpoint not wired to UI) |
| `AnalysisEngine._get_cached_mode_result()` | `analysis.py:566` | Only from `position_intelligence()` — itself dead from UI | **EFFECTIVELY DEAD** |
| `AnalysisEngine._run_position_intelligence()` | `analysis.py:468` | Only from `position_intelligence()` | **EFFECTIVELY DEAD** |
| `get_team_overview()` endpoint handler | `team.py:215` | Registered as FastAPI route, but no frontend caller | **POSSIBLY DEAD** (see Scan 3) |
| `_parse_json()` in `document_processor.py` | `document_processor.py:398` | `classify_and_extract()` within same file | USED |
| `_parse_json()` in `analysis.py` | `analysis.py:1162` | `_call_with_validation()` and `_score_candidate_batch()` within same file | USED |
| `try_link_report_to_team_member()` | `team.py:367` | `job_queue.py:178` — called after document processing | USED |
| `_build_overview()` | `team.py:66` | `list_team()` and `get_team_overview()` | Partially used |
| `_enrich()` | `projects.py:20` | All 4 project endpoints | USED |
| `data_sufficiency_check()` | `analysis.py:283` | `api/analysis.py` and `_check_sufficiency()` | USED |
| `get_analysis_engine()` | `analysis.py:1172` | `api/analysis.py`, `api/candidates.py` | USED |
| `_compress_resume()` | `analysis.py:986` | `candidate_score()` line 647 and `_score_candidate_batch()` line 854 | USED |
| `batch_candidate_score()` | `analysis.py:802` | `api/candidates.py:438` | USED |
| `get_context_for_analysis()` | `retrieval.py:131` | `analysis.py` (used via `self._retrieval`) | USED |
| `_sync_skills_from_resume()` | `team.py:94` | `add_team_member()` and `upload_resume()` | USED |
| `_reports_for_member()` | `team.py:23` | `_member_to_response()` and `get_member_reports()` | USED |

**Confirmed possibly unused: 3** (`VectorStore.count()`, `position_intelligence()` stack, `get_team_overview()` route handler)

---

### Scan 3 — Dead API Endpoints

| Endpoint | Path | Frontend reference in `api.ts` | Called from page? | Verdict |
|---|---|---|---|---|
| `POST /api/analysis/talent-brief` | analysis.py:73 | `runTalentBrief` | `projects/[id]/page.tsx` | ALIVE |
| `POST /api/analysis/historical-match` | analysis.py:91 | `runHistoricalMatch` | `projects/[id]/page.tsx` | ALIVE |
| `POST /api/analysis/level-advisor` | analysis.py:108 | `runLevelAdvisor` | `projects/[id]/page.tsx` | ALIVE |
| `POST /api/analysis/position-intelligence` | analysis.py:125 | Not in `api.ts` | Not called anywhere | **POSSIBLY DEAD** |
| `POST /api/analysis/candidate-score` | analysis.py:144 | `runCandidateScore` | `projects/[id]/page.tsx` | ALIVE |
| `POST /api/analysis/jd-reality-check` | analysis.py:163 | `runJDRealityCheck` | `projects/[id]/page.tsx`, `positions/[id]/page.tsx` | ALIVE |
| `GET /api/analysis/sufficiency/{project_id}/{mode}` | analysis.py:182 | `getSufficiency` | `projects/[id]/page.tsx` | ALIVE |
| `GET /api/analysis/results/{project_id}` | analysis.py:195 | `getAnalysisResults` | `projects/[id]/page.tsx`, `positions/[id]/page.tsx` | ALIVE |
| `GET /api/analysis/results/detail/{result_id}` | analysis.py:206 | `getAnalysisResult` | `candidates/[id]/page.tsx` | ALIVE |
| `POST /api/search` | search.py:39 | `search` (exported but never imported by pages) | Not called anywhere | **POSSIBLY DEAD** |
| `GET /api/projects/{project_id}/candidates` | candidates.py:474 | `getProjectCandidates` (exported but never imported by pages) | Not called anywhere | **POSSIBLY DEAD** |
| `GET /api/projects/{project_id}/team/overview` | team.py:214 | Not in `api.ts` | Not called anywhere | **POSSIBLY DEAD** |
| `POST /api/team/{member_id}/link-report/{document_id}` | team.py:341 | `linkReportToMember` | `projects/[id]/page.tsx:581` | ALIVE |
| `POST /api/team/{member_id}/sync-skills` | team.py:355 | `syncTeamMemberSkills` | Not called in pages (only exported in `api.ts`) | Ambiguous — exported but not used in current pages |
| All other document, project, position, candidate, job, team endpoints | various | Present in `api.ts` and called from pages | ALIVE | |

**Confirmed possibly dead: 3** (`/api/analysis/position-intelligence`, `POST /api/search`, `GET /api/projects/{project_id}/candidates`)
**Ambiguous: 2** (`/api/projects/{project_id}/team/overview`, `/api/team/{member_id}/sync-skills` — exported in api.ts but no page calls it)

> Note on `syncTeamMemberSkills`: it is exported in `api.ts` line 504 and called from `team/[id]/page.tsx` — search confirms this on line:
> `frontend/src/app/team/[id]/page.tsx` imports `syncTeamMemberSkills` and calls it. It is ALIVE.

---

### Scan 4 — Orphan Frontend Components

All components in `frontend/src/components/` are either UI primitives (shadcn) or application-level components. Application-level components:

| Component file | Exported name(s) | Imported by | Verdict |
|---|---|---|---|
| `components/nav.tsx` | `Nav` | `app/layout.tsx` | USED |
| `components/providers.tsx` | `Providers` | `app/layout.tsx` | USED |
| `components/ui/alert.tsx` | `Alert`, `AlertDescription`, `AlertTitle` | `pipeline/page.tsx`, `projects/[id]/page.tsx`, `positions/[id]/page.tsx`, `team/[id]/page.tsx` | USED |
| `components/ui/badge.tsx` | `Badge` | Multiple pages | USED |
| `components/ui/button.tsx` | `Button` | Multiple pages | USED |
| `components/ui/card.tsx` | `Card`, `CardContent`, `CardHeader`, `CardTitle` | Multiple pages | USED |
| `components/ui/dialog.tsx` | `Dialog`, `DialogContent`, `DialogHeader`, `DialogTitle` | Multiple pages | USED |
| `components/ui/dropdown-menu.tsx` | `DropdownMenu` and sub-exports | No app page imports it | **ORPHAN** |
| `components/ui/input.tsx` | `Input` | Multiple pages | USED |
| `components/ui/progress.tsx` | `Progress` | `projects/[id]/page.tsx` | USED |
| `components/ui/select.tsx` | `Select`, etc. | Multiple pages | USED |
| `components/ui/separator.tsx` | `Separator` | No app page imports it | **ORPHAN** |
| `components/ui/table.tsx` | `Table`, etc. | `pipeline/page.tsx` | USED |
| `components/ui/tabs.tsx` | `Tabs`, etc. | `projects/[id]/page.tsx` | USED |
| `components/ui/textarea.tsx` | `Textarea` | `candidates/[id]/page.tsx` | USED |

**Orphan components: 2** (`dropdown-menu.tsx`, `separator.tsx`)

---

### Scan 5 — Unused Pydantic Schema Fields

#### `ProjectResponse` (schemas.py:17)

| Field | Backend sets it? | Frontend reads it? | Verdict |
|---|---|---|---|
| `open_positions_count` | Yes — `projects.py:56` | Yes — `page.tsx:83,220` | USED |
| `total_candidates_count` | Yes — `projects.py:57` | Yes — `page.tsx:89,221` | USED |
| `avg_days_open` | Yes — `projects.py:58` | Defined in `api.ts:16` but never rendered in any page | **STALE — frontend never renders it** |
| `health_status` | Yes — `projects.py:59` | Yes — `page.tsx:109,112` | USED |
| `team_members_count` | Yes — `projects.py:60` | Yes — `page.tsx:77,80` | USED |

#### `CandidateResponse` (schemas.py:270)

| Field | Backend sets it? | Frontend reads it? | Verdict |
|---|---|---|---|
| `skill_match_score` | Yes — `candidates.py:118` | Yes — `candidates/[id]/page.tsx:537`, `positions/[id]/page.tsx:725` | USED |
| `scored_at` | Yes — `candidates.py:119` | Yes — `candidates/[id]/page.tsx:551` | USED |
| `resume_extracted` | Yes — `candidates.py:120` | Yes — `positions/[id]/page.tsx:516` | USED |
| `margin` | Yes — `candidates.py:121` | Yes — `candidates/[id]/page.tsx:233`, `positions/[id]/page.tsx:684` | USED |
| `tags` | Yes — `candidates.py:114` | In `api.ts:65` but **never rendered in any page** | **STALE — frontend never reads or displays it** |
| `availability` | Yes — `candidates.py:109` | In `api.ts:60` but no page renders `candidate.availability` | **STALE — frontend never reads it** |

#### `PositionResponse` (schemas.py:212)

| Field | Backend sets it? | Frontend reads it? | Verdict |
|---|---|---|---|
| `jd_processing_status` | Yes — `positions.py:76` | Yes — `projects/[id]/page.tsx:1485`, `positions/[id]/page.tsx:240` | USED |
| `jd_job_id` | Yes — `positions.py:77` | Defined in `api.ts:34` but **no page references `jd_job_id`** | **STALE — never used in frontend** |
| `jd_summary` | Yes — `positions.py:78` | Yes — `projects/[id]/page.tsx:1565-1567`, `positions/[id]/page.tsx:241` | USED |
| `closed_at` | Yes — ORM field | Defined in `api.ts:31` but **no page renders `closed_at`** | **STALE — never used in frontend** |
| `client_rate` / `client_rate_currency` / `client_rate_period` | Yes | Yes — `positions/[id]/page.tsx:1040-1041`, `candidates/[id]/page.tsx:226` | USED |

#### `TeamMemberResponse` (schemas.py:359)

| Field | Backend sets it? | Frontend reads it? | Verdict |
|---|---|---|---|
| `resume_summary` | Yes — `team.py:60` | Defined in `api.ts:99` but **no page renders `resume_summary`** | **STALE — frontend never reads it** |
| `reports_count` | Yes — `team.py:61` | Yes — `projects/[id]/page.tsx:1771` | USED |
| `last_report_date` | Yes — `team.py:62` | Yes — `projects/[id]/page.tsx:1703` | USED |

**Stale schema fields: 5** (`ProjectResponse.avg_days_open`, `CandidateResponse.tags`, `CandidateResponse.availability`, `PositionResponse.jd_job_id`, `PositionResponse.closed_at`, `TeamMemberResponse.resume_summary`)

> Note: `TeamMemberList.overview` — the `overview` field is returned and used in `projects/[id]/page.tsx:1821`. USED.

---

### Scan 6 — Duplicate Code Blocks

| Pattern | Locations | Notes |
|---|---|---|
| `_parse_json(text: str) -> dict` | `backend/app/services/document_processor.py:398` AND `backend/app/services/analysis.py:1162` | **Exact duplicate logic**: both strip markdown fences (```` ``` ````), take inner lines, and call `json.loads()`. The implementations are byte-for-byte identical in logic. `document_processor.py` version is the original; `analysis.py` redefined it locally rather than importing. |
| File upload + save + enqueue pattern | `api/documents.py`, `api/candidates.py`, `api/positions.py`, `api/team.py` | Structurally similar (hashlib sha256 → dedup check → uuid filename → write bytes → Document() → ProcessingJob() → enqueue). Not identical but highly repetitive. Low priority to extract since each has minor variations. |
| Score/verdict extraction | `api/candidates.py:366-368` and `api/candidates.py:447-450` | Same two-line `raw_score`/`raw_verdict` fallback pattern duplicated in `score_candidate` and `score_all_candidates`. |

**Confirmed identical duplicates: 1** (`_parse_json` in document_processor.py vs analysis.py)

The `_parse_json` in `analysis.py` could be replaced with:
```python
from app.services.document_processor import _parse_json
```
or extracted to a shared `app/utils/json_utils.py`.

---

### Scan 7 — Possibly Unused DB Model Columns

| Model | Column | Referenced outside `database.py`? | Verdict |
|---|---|---|---|
| `AICallLog` | `provider` | Yes — `groq_provider.py:117` (write) | WRITE-ONLY — never read |
| `AICallLog` | `model` | Yes — `groq_provider.py:118` (write) | WRITE-ONLY — never read |
| `AICallLog` | `endpoint` | Yes — `groq_provider.py:119` (write) | WRITE-ONLY — never read |
| `AICallLog` | `prompt_hash` | Yes — `groq_provider.py:120` (write) | WRITE-ONLY — never read |
| `AICallLog` | `input_tokens` | Yes — `groq_provider.py:121` (write) | WRITE-ONLY — never read |
| `AICallLog` | `output_tokens` | Yes — `groq_provider.py:122` (write) | WRITE-ONLY — never read |
| `AICallLog` | `latency_ms` | Yes — `groq_provider.py:123` (write) | WRITE-ONLY — never read |
| `AICallLog` | `cost_estimate` | Yes — `groq_provider.py:125` (write) | WRITE-ONLY — never read |
| `AICallLog` | `status` | Yes — `groq_provider.py:124` (write) | WRITE-ONLY — never read |
| `Candidate` | `availability` | Written in `CandidateUpdate` / `candidates.py`, returned in `CandidateResponse` | Frontend never renders — functionally invisible to user |
| `Candidate` | `tags` | Written via `CandidateUpdate`, returned in `CandidateResponse` | Frontend never renders — functionally invisible to user |
| `Position` | `closed_at` | Set in `update_position` when status becomes `closed`/`filled` | Not read by frontend — never displayed |
| `Project` (none) | All columns | Used by backend + frontend | OK |
| `Document` | `content_hash` | Used for dedup in all upload handlers; returned in API response | Frontend receives it but does not display it — dedup logic is server-side. Not dead — content_hash is essential. |
| `ExtractedData` | `extraction_prompt_version`, `schema_version` | Written in `job_queue.py:128-130` | Never read by any API endpoint, service, or frontend | **WRITE-ONLY metadata** |

**Confirmed write-only (never read via any API or service): 1 table** — `AICallLog` (entire table is write-only from application perspective; no API endpoint or service reads from it)

**Other write-only DB columns: 2** — `ExtractedData.extraction_prompt_version` and `ExtractedData.schema_version` written in `job_queue.py` but never queried or returned in any response schema.

---

## Notes on Frontend-Only Issues

### `salary_expectation` Field Mismatch

The TypeScript `Candidate` interface in `api.ts` declares `salary_expectation?: string` (line 58). The `updateCandidate` options also include `salary_expectation` (line 441). The candidates detail page (`candidates/[id]/page.tsx` lines 626–628) renders an editable field for it and sends it in PATCH requests.

However, there is **no `salary_expectation` column in the `Candidate` SQLAlchemy model**, no field in `CandidateUpdate` Pydantic schema, and no field in `CandidateResponse`. When the frontend sends `salary_expectation` in a `PUT /api/candidates/{id}` body, `CandidateUpdate` will silently ignore it (Pydantic ignores extra keys by default, and the update loop in `candidates.py:308-317` only iterates over the hardcoded field list).

**Effect:** The field is sent but never persisted. The UI shows an empty box that appears editable but saves nothing.
