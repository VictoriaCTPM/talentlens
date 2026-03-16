/**
 * Shared helpers for TalentLens E2E tests.
 * All API calls go directly to the backend (http://localhost:8000/api)
 * so we can set up and tear down state without going through the UI.
 */

const API = "http://localhost:8000/api";

// ── API helpers ───────────────────────────────────────────────────────────────

export async function apiPost<T>(path: string, body: object): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} → ${res.status}: ${await res.text()}`);
  return res.json();
}

export async function apiDelete(path: string): Promise<void> {
  const res = await fetch(`${API}${path}`, { method: "DELETE" });
  if (!res.ok && res.status !== 404) throw new Error(`DELETE ${path} → ${res.status}`);
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
  return res.json();
}

// ── Fixture factories ─────────────────────────────────────────────────────────

export interface Project { id: number; name: string; client_name: string; }
export interface Position { id: number; title: string; project_id: number; }
export interface Candidate { id: number; name: string; position_id: number; }
export interface TeamMember { id: number; name: string; project_id: number; }

export async function createProject(name = "E2E Project", client = "E2E Client"): Promise<Project> {
  return apiPost("/projects", { name, client_name: client, description: "Created by E2E test" });
}

export async function deleteProject(id: number): Promise<void> {
  return apiDelete(`/projects/${id}`);
}

export async function createPosition(projectId: number, title = "Senior Engineer"): Promise<Position> {
  const fd = new FormData();
  fd.append("title", title);
  fd.append("level", "senior");
  const res = await fetch(`${API}/projects/${projectId}/positions`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(`createPosition → ${res.status}: ${await res.text()}`);
  return res.json();
}

export async function createCandidate(positionId: number, name = "Alice Smith"): Promise<Candidate> {
  const fd = new FormData();
  fd.append("name", name);
  const res = await fetch(`${API}/positions/${positionId}/candidates`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(`createCandidate → ${res.status}: ${await res.text()}`);
  return res.json();
}

export async function createTeamMember(projectId: number, name = "Bob Dev"): Promise<TeamMember> {
  const fd = new FormData();
  fd.append("name", name);
  fd.append("role", "developer");
  fd.append("level", "mid");
  const res = await fetch(`${API}/projects/${projectId}/team`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(`createTeamMember → ${res.status}: ${await res.text()}`);
  return res.json();
}

/** Upload a small text file as a document to a project. Returns document id. */
export async function uploadTextDocument(
  projectId: number,
  content = "Skills: TypeScript, React, Node.js\nExperience: 5 years",
  docType = "resume",
  filename = "test_resume.txt",
): Promise<number> {
  const fd = new FormData();
  fd.append("file", new Blob([content], { type: "text/plain" }), filename);
  fd.append("doc_type", docType);
  const res = await fetch(`${API}/projects/${projectId}/documents`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(`uploadDocument → ${res.status}: ${await res.text()}`);
  const doc = await res.json();
  return doc.id;
}

/** Poll job until completed or timeout (ms). */
export async function waitForJob(jobId: number, timeoutMs = 30_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const job = await apiGet<{ status: string }>(`/jobs/${jobId}`);
    if (job.status === "completed") return;
    if (job.status === "failed") throw new Error(`Job ${jobId} failed`);
    await new Promise((r) => setTimeout(r, 800));
  }
  throw new Error(`Job ${jobId} timed out`);
}
