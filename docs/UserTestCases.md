# TalentLens — User Test Cases

**Product:** TalentLens (AI-powered Talent Intelligence Platform)
**Scope:** Manual end-to-end user testing
**Environment:** localhost:3000 (frontend) + localhost:8000 (backend)

---

## Module 1 — Dashboard & Projects

### TC-01 | Create a new project
**Steps:**
1. Open the Dashboard (`/`)
2. Click "New Project"
3. Fill in: Name = "Test Project", Client = "Acme Corp", Description = "QA test"
4. Click "Create"

**Expected:** Project card appears in the list; counters show 0 positions, 0 candidates.

---

### TC-02 | Dashboard stats reflect real data
**Steps:**
1. Create a project with 1 open position and 2 candidates
2. Return to Dashboard (`/`)

**Expected:** "Active Projects" counter increments; stats cards show correct totals.

---

### TC-03 | Edit a project
**Steps:**
1. Open a project → click "Edit Project"
2. Change client name → Save

**Expected:** Updated client name shown in header and on Dashboard card.

---

### TC-04 | Delete a project
**Steps:**
1. On the Dashboard, click the delete icon on a project card
2. Confirm deletion

**Expected:** Project removed from list; all associated documents/positions/candidates also gone.

---

### TC-05 | Project health status
**Steps:**
1. Create a project with a position open for 25+ days (or wait / manually adjust DB date)
2. Open Dashboard

**Expected:** Project card shows "At Risk" or "Attention" badge, not "Healthy".

---

## Module 2 — Documents

### TC-06 | Upload a PDF document
**Steps:**
1. Open a project → Documents tab
2. Click "Upload" → select a PDF file ≤ 50 MB
3. Wait for processing to complete

**Expected:** Document appears in list with status "processed"; file type shows "pdf".

---

### TC-07 | Upload a TXT document
**Steps:**
1. Upload a `.txt` resume file to a project

**Expected:** Document processed; doc_type auto-classified (e.g. "resume").

---

### TC-08 | File size limit enforcement
**Steps:**
1. Try to upload a file larger than 50 MB

**Expected:** Error message "File too large (N MB). Maximum allowed size is 50 MB."

---

### TC-09 | Duplicate file detection
**Steps:**
1. Upload the same file twice to the same project

**Expected:** Second upload returns the existing document (no duplicate entry created).

---

### TC-10 | Document preview
**Steps:**
1. Upload a resume document
2. Click the eye icon (👁) on the document row

**Expected:** Preview panel slides in on the right, showing structured content (Summary, Skills, Experience, Education).

---

### TC-11 | Download a document
**Steps:**
1. Click the download icon (⬇) on any document row

**Expected:** File download starts in the browser.

---

### TC-12 | Delete a document
**Steps:**
1. Click the delete icon on a document row → confirm

**Expected:** Document removed from list; no orphan file on disk.

---

## Module 3 — Positions

### TC-13 | Create a position with JD upload
**Steps:**
1. Open a project → Positions tab → "Add Position"
2. Enter title, select level, upload a JD file
3. Submit

**Expected:** Position created; JD processing starts (status shows "processing" then "processed").

---

### TC-14 | Create a position without JD
**Steps:**
1. Add a position with only a title (no file)

**Expected:** Position created with no JD; JD processing status is empty.

---

### TC-15 | Replace JD on existing position
**Steps:**
1. Open a position that already has a JD
2. Click "Replace JD" → upload a new file

**Expected:** New JD linked; old JD document remains in project documents.

---

### TC-16 | Edit position details
**Steps:**
1. Open a position → edit title / level / status

**Expected:** Changes saved and reflected on the position card.

---

### TC-17 | Close a position
**Steps:**
1. Change position status to "closed"

**Expected:** Position no longer counts as "open" in project stats; Pipeline page does not show it.

---

### TC-18 | Delete a position
**Steps:**
1. Delete a position that has candidates

**Expected:** Position and all its candidates are removed.

---

## Module 4 — Pipeline Monitor

### TC-19 | View open positions pipeline
**Steps:**
1. Open `/pipeline`

**Expected:** All open positions across all projects are listed with: title, project, client, days open, candidate count.

---

### TC-20 | Critical positions highlighted
**Steps:**
1. Ensure at least one position has been open for 30+ days
2. Open `/pipeline`

**Expected:** That position is visually highlighted (red/warning color or badge).

---

## Module 5 — Candidates

### TC-21 | Add a candidate with resume upload
**Steps:**
1. Open a position → Candidates tab → "Add Candidate"
2. Enter name, upload a resume file
3. Submit

**Expected:** Candidate appears in the list with status "New"; resume processing starts.

---

### TC-22 | Add a candidate without resume
**Steps:**
1. Add a candidate with name only (no file)

**Expected:** Candidate created; AI score fields are empty; "Upload resume to enable AI scoring" message shown on profile.

---

### TC-23 | Run AI analysis on a candidate
**Steps:**
1. Open a candidate that has a resume AND the parent position has a JD
2. Click "Run AI Analysis" (or "Re-analyze")

**Expected:** Score ring appears (0–100); verdict shown (e.g. "Strong Hire"); Key Arguments listed.

---

### TC-24 | AI analysis disabled without resume
**Steps:**
1. Open a candidate with no resume

**Expected:** "Re-analyze" button is disabled; tooltip or message explains why.

---

### TC-25 | Change candidate status
**Steps:**
1. On candidate profile, change status dropdown from "New" → "Screening"

**Expected:** Badge updates immediately; Timeline shows a "Status changed" event.

---

### TC-26 | Edit recruiter / interview / client notes
**Steps:**
1. Open candidate profile
2. Click on "Recruiter Notes" field → type text → click outside to save

**Expected:** Text saved; no page reload required.

---

### TC-27 | Margin calculator — enter rates
**Steps:**
1. On candidate profile, set Candidate Rate = 5000 / monthly
2. Set Client Rate = 7000 / monthly (on position)
3. Click "Save Rates"

**Expected:** Margin % and absolute value calculated and displayed; progress bar shown.

---

### TC-28 | Margin calculator — missing rate
**Steps:**
1. Set only Candidate Rate, leave Client Rate empty

**Expected:** "Missing: client rate — enter rates above to compute margin" message shown.

---

### TC-29 | Rejection reason field appears
**Steps:**
1. Change candidate status to "Rejected"

**Expected:** "Rejection Reason" card appears at the bottom of the right column.

---

### TC-30 | Candidate activity timeline
**Steps:**
1. Add a candidate → change status twice → run AI analysis

**Expected:** Timeline shows 3+ events in chronological order with correct labels.

---

### TC-31 | Batch score all candidates
**Steps:**
1. Open a position that has a JD and 2+ candidates with resumes
2. Click "Score All"

**Expected:** All candidates receive AI scores; list refreshes with scores visible.

---

### TC-32 | Delete a candidate
**Steps:**
1. Delete a candidate from the position candidates list

**Expected:** Candidate removed from list; no longer appears in project stats.

---

## Module 6 — AI Analysis (Position Level)

### TC-33 | Talent Brief (Mode A)
**Steps:**
1. Open a position with a processed JD
2. Go to Analysis tab → run "Talent Brief"

**Expected:** Result shows: required skills list, hiring tips, historical insights.

---

### TC-34 | Historical Match (Mode B)
**Steps:**
1. Run "Historical Match" on a position with a JD

**Expected:** Similar past positions listed with match rationale.

---

### TC-35 | Level Advisor (Mode C)
**Steps:**
1. Run "Level Advisor" on a JD

**Expected:** Recommended seniority level with justification returned.

---

### TC-36 | JD Reality Check (Mode E)
**Steps:**
1. Run "JD Reality Check" on a position JD

**Expected:** Analysis of unrealistic requirements / red flags in the JD.

---

### TC-37 | Sufficiency check blocks analysis
**Steps:**
1. Try to run an analysis on a position with no JD

**Expected:** Analysis button disabled or error message "Missing: job description".

---

## Module 7 — Team Members

### TC-38 | Add a team member
**Steps:**
1. Open a project → Team tab → "Add Member"
2. Enter name, role, level, start date → Submit

**Expected:** Member card appears in the Team tab.

---

### TC-39 | Add team member with resume
**Steps:**
1. Add a team member and upload a resume file at the same time

**Expected:** Member created; resume processed; skills auto-populated on member profile.

---

### TC-40 | Navigate to team member profile
**Steps:**
1. Click on a team member card in the Team tab

**Expected:** Browser navigates to `/team/{id}`; member name and details visible.

---

### TC-41 | Edit team member details
**Steps:**
1. On `/team/{id}` → click "Edit"
2. Change role → Save

**Expected:** Updated role shown in header and detail card.

---

### TC-42 | Sync skills from resume
**Steps:**
1. Open a team member who has a processed resume
2. In the Skills card → click "Sync from Resume"

**Expected:** Skills list updated from resume extracted data; button shows "Syncing…" during request.

---

### TC-43 | Upload / replace team member resume
**Steps:**
1. Open a team member with no resume → drag-drop a file into the upload zone

**Expected:** Resume uploaded; "Resume" section populates with extracted content.

---

### TC-44 | Back button on team member profile
**Steps:**
1. Navigate to `/team/{id}` via the Team tab
2. Click the back arrow (←)

**Expected:** Browser navigates back to the parent project page (not a dead-end blank page).

---

### TC-45 | Team member reports
**Steps:**
1. Upload a document classified as "report" and link it to a team member
2. Open team member profile → Reports section

**Expected:** Report document listed with date and preview of extracted tasks/blockers.

---

## Module 8 — Search

### TC-46 | Basic document search
**Steps:**
1. Open a project that has processed documents
2. Go to Search tab → type a keyword present in one of the documents

**Expected:** Results returned with matching text snippets and relevance scores.

---

### TC-47 | Search returns no results
**Steps:**
1. Search for a term that doesn't exist in any document

**Expected:** "No results" message shown; no error.

---

### TC-48 | Search scoped to project
**Steps:**
1. Upload a unique document to Project A
2. Search from Project B using the unique keyword

**Expected:** No results returned (search respects project scope).

---

## Module 9 — Edge Cases & Error Handling

### TC-49 | Invalid file type upload
**Steps:**
1. Try to upload an `.exe` or unsupported file type

**Expected:** Error shown; file rejected.

---

### TC-50 | API server offline
**Steps:**
1. Stop the backend server
2. Open the Dashboard

**Expected:** Graceful error state shown (not a blank/crashed page); user sees a message.

---

### TC-51 | Navigate directly to non-existent candidate
**Steps:**
1. Open `/candidates/99999` (non-existent ID)

**Expected:** "Candidate not found" message with a "Go back" button.

---

### TC-52 | Navigate directly to non-existent team member
**Steps:**
1. Open `/team/99999`

**Expected:** "Member not found" or similar error state shown.

---

## Test Coverage Summary

| Module | TCs | Key Risk Areas |
|---|---|---|
| Dashboard & Projects | TC-01–05 | Stats accuracy, delete cascade |
| Documents | TC-06–12 | Upload limits, dedup, preview |
| Positions | TC-13–18 | JD linking, status transitions |
| Pipeline | TC-19–20 | Cross-project aggregation |
| Candidates | TC-21–32 | AI scoring, status flow, margin calc |
| AI Analysis | TC-33–37 | All 4 modes + sufficiency guard |
| Team Members | TC-38–45 | Resume sync, navigation, reports |
| Search | TC-46–48 | Relevance, scoping |
| Edge Cases | TC-49–52 | Error handling, 404s |
| **Total** | **52** | |
