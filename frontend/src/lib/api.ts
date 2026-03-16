const API_BASE = "/api";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Project {
  id: number;
  name: string;
  client_name: string;
  description?: string;
  status: string;
  created_at: string;
  updated_at: string;
  // enriched stats
  open_positions_count: number;
  total_candidates_count: number;
  avg_days_open?: number;
  health_status: string;
  team_members_count: number;
}

export interface Position {
  id: number;
  project_id: number;
  title: string;
  level?: string;
  status: string;
  jd_document_id?: number;
  days_open: number;
  candidates_count: number;
  created_at: string;
  closed_at?: string;
  // JD enrichment
  jd_processing_status?: string;
  jd_job_id?: number;
  jd_summary?: Record<string, unknown>;
  // Rate fields
  client_rate?: number;
  client_rate_currency?: string;
  client_rate_period?: string;
}

export interface Candidate {
  id: number;
  position_id: number;
  name: string;
  email?: string;
  resume_document_id?: number;
  status: string;
  ai_score?: number;
  ai_verdict?: string;
  ai_analysis_id?: number;
  notes?: string;
  created_at: string;
  updated_at: string;
  // Profile fields
  phone?: string;
  years_of_experience?: number;
  location?: string;
  availability?: string;
  recruiter_notes?: string;
  interview_notes?: string;
  client_feedback?: string;
  rejection_reason?: string;
  tags?: string[];
  // Rate fields
  candidate_rate?: number;
  candidate_rate_currency?: string;
  candidate_rate_period?: string;
  // Computed enrichment
  skill_match_score?: number;
  scored_at?: string;
  resume_extracted?: Record<string, unknown>;
  margin?: Record<string, unknown>;
  team_member_id?: number;
}

export interface CandidateEvent {
  id: number;
  candidate_id: number;
  event_type: string;
  event_data?: Record<string, unknown>;
  created_at: string;
}

export interface TeamMember {
  id: number;
  project_id: number;
  name: string;
  role: string;
  level?: string;
  start_date?: string;
  status: string;
  resume_document_id?: number;
  skills?: string[];
  notes?: string;
  created_at: string;
  updated_at: string;
  // Computed fields
  resume_summary?: Record<string, unknown>;
  reports_count: number;
  last_report_date?: string;
  hired_from_candidate_id?: number;
  hired_from_position_id?: number;
}

export interface PipelinePosition {
  id: number;
  title: string;
  project_id: number;
  project_name: string;
  client_name: string;
  days_open: number;
  candidates_count: number;
  status: string;
  status_label: string;
}

export interface Document {
  id: number;
  project_id: number;
  filename: string;
  original_filename: string;
  file_type: string;
  doc_type?: string;
  file_size: number;
  status: string;
  error_message?: string;
  created_at: string;
  processed_at?: string;
  team_member_id?: number;
  developer_name_hint?: string;
}

export interface DocumentDetail extends Document {
  extracted_data: Array<{
    id: number;
    doc_type: string;
    structured_data: Record<string, unknown>;
    extraction_model: string;
    created_at: string;
  }>;
}

export interface UploadResponse extends Document {
  job_id: number;
}

export interface ProcessingJob {
  id: number;
  document_id: number;
  job_type: string;
  status: string;
  progress: number;
  error_message?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

export interface AnalysisResult {
  id: number;
  project_id: number;
  analysis_mode: string;
  input_document_ids: number[];
  result_data: Record<string, unknown>;
  confidence_score?: number;
  source_citations?: (string | Record<string, unknown>)[];
  model_used: string;
  prompt_version: string;
  created_at: string;
}

export interface SearchResult {
  chunk_id: string;
  text: string;
  metadata: Record<string, unknown>;
  bm25_score: number;
  vector_score: number;
  combined_score: number;
}

// ── Core fetch ────────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const isFormData = options?.body instanceof FormData;
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: isFormData ? { ...options?.headers } : { "Content-Type": "application/json", ...options?.headers },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const msg =
      typeof err.detail === "string"
        ? err.detail
        : Array.isArray(err.detail)
        ? err.detail.map((d: { msg?: string; loc?: string[] }) => `${(d.loc ?? []).slice(-1)[0]}: ${d.msg}`).join("; ")
        : err.detail?.message || `API error ${res.status}`;
    throw new Error(msg);
  }
  return res.json();
}

// ── Projects ──────────────────────────────────────────────────────────────────

export const getProjects = () =>
  apiFetch<{ items: Project[]; total: number }>("/projects");

export const getProject = (id: number) =>
  apiFetch<Project>(`/projects/${id}`);

export const createProject = (data: {
  name: string;
  client_name: string;
  description?: string;
}) => apiFetch<Project>("/projects", { method: "POST", body: JSON.stringify(data) });

export const updateProject = (
  id: number,
  data: { name: string; client_name: string; description?: string; status: string }
) =>
  apiFetch<Project>(`/projects/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });

export const deleteProject = (id: number) =>
  fetch(`${API_BASE}/projects/${id}`, { method: "DELETE" });

// ── Documents ─────────────────────────────────────────────────────────────────

export const getDocuments = (projectId: number) =>
  apiFetch<{ items: Document[]; total: number }>(
    `/projects/${projectId}/documents`
  );

export const getDocument = (id: number) =>
  apiFetch<DocumentDetail>(`/documents/${id}`);

export const deleteDocument = (id: number) =>
  fetch(`${API_BASE}/documents/${id}`, { method: "DELETE" });

export const downloadDocument = (id: number) =>
  `${API_BASE}/documents/${id}/download`;

export async function uploadDocument(
  projectId: number,
  file: File,
  docType?: string
): Promise<UploadResponse> {
  const fd = new FormData();
  fd.append("file", file);
  if (docType) fd.append("doc_type", docType);
  const res = await fetch(`${API_BASE}/projects/${projectId}/documents`, {
    method: "POST",
    body: fd,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Upload failed ${res.status}`);
  }
  return res.json();
}

// ── Jobs ──────────────────────────────────────────────────────────────────────

export const getJob = (id: number) =>
  apiFetch<ProcessingJob>(`/jobs/${id}`);

// ── Analysis ──────────────────────────────────────────────────────────────────

export const getSufficiency = (projectId: number, mode: string) =>
  apiFetch<{ can_run: boolean; missing: string[]; data_quality: string }>(
    `/analysis/sufficiency/${projectId}/${mode}`
  );

export const runTalentBrief = (documentId: number) =>
  apiFetch<Record<string, unknown>>("/analysis/talent-brief", {
    method: "POST",
    body: JSON.stringify({ document_id: documentId }),
  });

export const runHistoricalMatch = (documentId: number) =>
  apiFetch<Record<string, unknown>>("/analysis/historical-match", {
    method: "POST",
    body: JSON.stringify({ document_id: documentId }),
  });

export const runLevelAdvisor = (documentId: number) =>
  apiFetch<Record<string, unknown>>("/analysis/level-advisor", {
    method: "POST",
    body: JSON.stringify({ document_id: documentId }),
  });

export const runCandidateScore = (resumeDocId: number, jdDocId: number) =>
  apiFetch<Record<string, unknown>>("/analysis/candidate-score", {
    method: "POST",
    body: JSON.stringify({
      resume_document_id: resumeDocId,
      jd_document_id: jdDocId,
    }),
  });

export const runJDRealityCheck = (documentId: number) =>
  apiFetch<Record<string, unknown>>("/analysis/jd-reality-check", {
    method: "POST",
    body: JSON.stringify({ document_id: documentId }),
  });

export const getAnalysisResults = (projectId: number) =>
  apiFetch<AnalysisResult[]>(`/analysis/results/${projectId}`);

export const getAnalysisResult = (id: number) =>
  apiFetch<AnalysisResult>(`/analysis/results/detail/${id}`);

// ── Search ────────────────────────────────────────────────────────────────────

// search() removed — endpoint /api/search exists but no UI yet

// ── Positions ─────────────────────────────────────────────────────────────────

export const getPositions = (projectId: number) =>
  apiFetch<{ items: Position[]; total: number }>(`/projects/${projectId}/positions`);

export const getPosition = (id: number) =>
  apiFetch<Position>(`/positions/${id}`);

export async function createPosition(data: {
  title?: string;
  project_id: number;
  jd_document_id?: number;
  level?: string;
  file?: File;
}): Promise<Position> {
  const fd = new FormData();
  if (data.title) fd.append("title", data.title);
  if (data.level) fd.append("level", data.level);
  if (data.jd_document_id) fd.append("jd_document_id", String(data.jd_document_id));
  if (data.file) fd.append("file", data.file);

  const res = await fetch(`${API_BASE}/projects/${data.project_id}/positions`, {
    method: "POST",
    body: fd,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to create position ${res.status}`);
  }
  return res.json();
}

export async function replacePositionJd(
  positionId: number,
  data: { jd_document_id?: number; file?: File }
): Promise<Position> {
  const fd = new FormData();
  if (data.jd_document_id) fd.append("jd_document_id", String(data.jd_document_id));
  if (data.file) fd.append("file", data.file);

  const res = await fetch(`${API_BASE}/positions/${positionId}/jd`, {
    method: "PUT",
    body: fd,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to update JD ${res.status}`);
  }
  return res.json();
}

export const updatePosition = (id: number, data: {
  title?: string; status?: string; level?: string;
  client_rate?: number; client_rate_currency?: string; client_rate_period?: string;
}) =>
  apiFetch<Position>(`/positions/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });

export const deletePosition = (id: number) =>
  fetch(`${API_BASE}/positions/${id}`, { method: "DELETE" });

export const getPipeline = () =>
  apiFetch<PipelinePosition[]>("/pipeline");

// ── Candidates ────────────────────────────────────────────────────────────────

export const getCandidates = (positionId: number) =>
  apiFetch<{ items: Candidate[]; total: number }>(`/positions/${positionId}/candidates`);

export const getCandidate = (id: number) =>
  apiFetch<Candidate>(`/candidates/${id}`);

export async function addCandidate(
  positionId: number,
  data: { name?: string; email?: string; resume_document_id?: number; notes?: string },
  file?: File
): Promise<Candidate> {
  const fd = new FormData();
  if (data.name) fd.append("name", data.name);
  if (data.email) fd.append("email", data.email);
  if (data.resume_document_id) fd.append("resume_document_id", String(data.resume_document_id));
  if (data.notes) fd.append("notes", data.notes);
  if (file) fd.append("file", file);

  const res = await fetch(`${API_BASE}/positions/${positionId}/candidates`, {
    method: "POST",
    body: fd,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to add candidate ${res.status}`);
  }
  return res.json();
}

export const getCandidateTimeline = (id: number) =>
  apiFetch<CandidateEvent[]>(`/candidates/${id}/timeline`);

export const updateCandidate = (id: number, data: {
  status?: string; notes?: string; email?: string; name?: string;
  phone?: string;
  years_of_experience?: number; location?: string;
  availability?: string; recruiter_notes?: string;
  interview_notes?: string; client_feedback?: string; rejection_reason?: string;
  tags?: string[];
  candidate_rate?: number; candidate_rate_currency?: string; candidate_rate_period?: string;
}) =>
  apiFetch<Candidate>(`/candidates/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });

export const deleteCandidate = (id: number) =>
  fetch(`${API_BASE}/candidates/${id}`, { method: "DELETE" });

export const scoreCandidate = (id: number) =>
  apiFetch<Candidate>(`/candidates/${id}/score`, { method: "POST" });

export const scoreAllCandidates = (positionId: number) =>
  apiFetch<Candidate[]>(`/positions/${positionId}/score-all`, { method: "POST" });

// ── Team ──────────────────────────────────────────────────────────────────────

export const getTeam = (projectId: number) =>
  apiFetch<{ items: TeamMember[]; total: number; overview: Record<string, unknown> | null }>(`/projects/${projectId}/team`);

export const getTeamMember = (memberId: number) =>
  apiFetch<TeamMember>(`/team/${memberId}`);

export interface MemberReport {
  id: number;
  original_filename: string;
  doc_type: string;
  file_size: number;
  status: string;
  created_at: string;
  extracted: Record<string, unknown> | null;
}

export const getMemberReports = (memberId: number) =>
  apiFetch<{ items: MemberReport[]; total: number }>(`/team/${memberId}/reports`);

export const uploadTeamMemberResume = (memberId: number, file: File) => {
  const fd = new FormData();
  fd.append("file", file);
  return apiFetch<TeamMember>(`/team/${memberId}/resume`, { method: "POST", body: fd });
};

export const addTeamMember = (projectId: number, formData: FormData) =>
  apiFetch<TeamMember>(`/projects/${projectId}/team`, {
    method: "POST",
    body: formData,
  });

export const updateTeamMember = (memberId: number, data: Partial<TeamMember>) =>
  apiFetch<TeamMember>(`/team/${memberId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });

export const deleteTeamMember = (memberId: number) =>
  apiFetch<void>(`/team/${memberId}`, { method: "DELETE" });

export const syncTeamMemberSkills = (memberId: number) =>
  apiFetch<TeamMember>(`/team/${memberId}/sync-skills`, { method: "POST" });

export const linkReportToMember = (memberId: number, documentId: number) =>
  apiFetch<Record<string, unknown>>(`/team/${memberId}/link-report/${documentId}`, {
    method: "POST",
  });
