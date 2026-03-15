# TalentLens — Design System & UI Specification
> Version: 1.0 | Date: 2026-03-09 | Source: Lovable AI + architectural review

## 1. Layout Architecture

### Shell
- Fixed top navigation: logo (TalentLens icon + wordmark) + nav links (Dashboard, Pipeline) + user avatar (initials circle, top-right)
- No sidebar — maximizes content density
- Content container: max-width 1400px, centered, padding 24px
- Background: light gray (Tailwind `bg-gray-50`)

### Screen Flow
Dashboard (home) ├── Project Card → Project Detail │ ├── Tab: Documents (upload + file list) │ ├── Tab: AI Analysis (Modes A/B/C/D) │ ├── Tab: Candidates (ranking table) │ └── Tab: Timeline / Activity │ Pipeline Monitor (top-nav link, cross-project view) │ Candidate Detail (deep-dive from ranking table)


## 2. Color System
| Token | Value | Usage |
|-------|-------|-------|
| Primary | #0D9488 (teal-600) | Actions, active nav, badges |
| Primary hover | #0F766E (teal-700) | Hover states |
| Background | #F8F9FA | Page background |
| Card | #FFFFFF | Card backgrounds |
| Border | #E5E7EB | Cards, table dividers |
| Text primary | #111827 | Headings |
| Text secondary | #6B7280 | Labels, metadata |
| Status green | #10B981 | Healthy / On Track |
| Status yellow | #F59E0B | Attention / Slow |
| Status red | #EF4444 | At Risk / Critical |

## 3. Key Components

### Project Card
- White card, border, rounded-xl, p-6
- Header: project name (18px semibold) + client (14px gray) + status dot
- Metrics: open roles, candidates, last active
- Footer: status badge pill (active=teal, completed=gray)
- Grid: 2 columns desktop, 1 column mobile

### Pipeline Monitor Table
- Sorted by days open (worst first)
- Color-coded days: >30=red, 20-30=yellow, <20=gray
- Alert banner for critical positions
- Columns: Role, Project, Client, Days Open, Candidates, Status

### AI Analysis Cards (Modes A/B/C/D)
- Mode badge (colored pill: A=teal, B=blue, C=purple, D=orange)
- Confidence bar (horizontal progress + %)
- Structured sections with scannable content
- Skill tags as rounded pills
- Source citations footer
- Warning strip if data insufficient

### Candidate Score Card
- Large score circle (48px, color-coded)
- Verdict badge (Strong Fit / Risky / Not Recommended)
- Breakdown bars (Skills / Experience / Team Fit)
- Strengths as green chips, Gaps as red chips
- Historical comparison quote block

### Document Upload
- Dashed border drop zone
- Files grouped by type with section headers
- Status: queued (gray) → processing (teal spinner) → done (green check)

## 4. Typography
- Font: Inter / system sans-serif
- Page title: 28px/700, Card title: 18px/600
- Metric number: 32px/700, Body: 14px/400
- Labels: 12px/400-500

## 5. Icons
- Library: Lucide React (included with shadcn/ui)
- Key: Building2, Users, Clock, Upload, FileText, AlertTriangle, CheckCircle, XCircle, Loader2, Search, BarChart3
Position Card (inside project detail)

┌─────────────────────────────────────────────────────┐
│  Senior Backend Engineer          ● Open   Day 18   │
│  From JD: backend-engineer-jd.pdf                   │
│                                                      │
│  👤 4 candidates   ✅ 2 scored   ⏳ 2 pending       │
│                                                      │
│  Top candidate: Sarah Chen — 84 pts, Strong Fit     │
│                                                      │
│  [View Candidates]  [Run AI Analysis]  [Close]      │
└─────────────────────────────────────────────────────┘
Add Candidate Dialog

┌─────────────────────────────────────────┐
│  Add Candidate                     [x]  │
│                                         │
│  Position: Senior Backend Engineer      │
│                                         │
│  ○ Upload new resume                    │
│    ┌─────────────────────────────┐      │
│    │  Drag & drop PDF/DOC here  │      │
│    └─────────────────────────────┘      │
│                                         │
│  ○ Choose existing resume               │
│    ┌─────────────────────────────┐      │
│    │  🔍 Search uploaded resumes │      │
│    │  ☐ Alex Johnson (resume.pdf)│      │
│    │  ☐ Maria Lopez (ml-cv.doc)  │      │
│    └─────────────────────────────┘      │
│                                         │
│  [Cancel]              [Add Candidate]  │
└─────────────────────────────────────────┘
Candidate Row in Position Detail

| # | Name          | Score | Skills | Exp  | Verdict       | Status              | Actions        |
|---|---------------|-------|--------|------|---------------|---------------------|----------------|
| 1 | Sarah Chen    | 84    | 78%    | 91%  | ✅ Strong Fit  | Technical Interview | [View] [▼]     |
| 2 | Alex Johnson  | 71    | 82%    | 65%  | ✅ Strong Fit  | Screening           | [View] [▼]     |
| 3 | Maria Lopez   | 45    | 40%    | 55%  | ❌ Not Rec.    | Rejected            | [View] [▼]     |
| — | James Wilson  | —     | —      | —    | ⏳ Pending     | New                 | [Score] [▼]    |
