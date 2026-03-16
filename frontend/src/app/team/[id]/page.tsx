"use client";

import { useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Upload,
  FileText,
  Loader2,
  CheckCircle,
  Download,
  ChevronDown,
  ChevronUp,
  Pencil,
  RefreshCw,
  Users,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  getTeamMember,
  getMemberReports,
  updateTeamMember,
  uploadTeamMemberResume,
  syncTeamMemberSkills,
  getDocument,
  downloadDocument,
  type MemberReport,
} from "@/lib/api";

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatBytes(n: number) {
  return n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1048576).toFixed(1)} MB`;
}

function formatDate(d?: string | null) {
  if (!d) return "—";
  return new Date(d).toLocaleDateString("en-US", { month: "long", year: "numeric" });
}

function formatShortDate(d?: string | null) {
  if (!d) return "";
  return new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

// ── Resume Content ────────────────────────────────────────────────────────────

function ResumeContent({ documentId }: { documentId: number }) {
  const { data: doc, isLoading } = useQuery({
    queryKey: ["document-detail", documentId],
    queryFn: () => getDocument(documentId),
    refetchInterval: (q) => {
      return q.state.data?.status === "queued" || q.state.data?.status === "processing" ? 2000 : false;
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-10">
        <Loader2 className="w-5 h-5 animate-spin text-teal-500" />
      </div>
    );
  }

  if (!doc) return null;

  if (doc.status === "queued" || doc.status === "processing") {
    return (
      <div className="flex flex-col items-center justify-center py-10 text-center">
        <Loader2 className="w-6 h-6 animate-spin text-teal-400 mb-2" />
        <p className="text-sm text-gray-500">Processing resume…</p>
      </div>
    );
  }

  const extracted = doc.extracted_data?.[0]?.structured_data as Record<string, unknown> | undefined;

  return (
    <>
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs text-gray-400">{doc.original_filename} · {formatBytes(doc.file_size)}</p>
        <a
          href={downloadDocument(doc.id)}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs px-2.5 py-1 rounded-md bg-teal-600 text-white hover:bg-teal-700 flex items-center gap-1"
        >
          <Download className="w-3 h-3" /> Download
        </a>
      </div>

      {!extracted ? (
        <p className="text-sm text-gray-400 py-4 text-center">No extracted content available.</p>
      ) : (
        <div className="space-y-4">
          {extracted.summary != null && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Summary</p>
              <p className="text-sm text-gray-700 leading-relaxed">{String(extracted.summary)}</p>
            </div>
          )}
          {(extracted.work_history != null || extracted.experience != null) && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Experience</p>
              <div className="space-y-2 mt-1">
                {(Array.isArray(extracted.work_history) ? extracted.work_history : Array.isArray(extracted.experience) ? extracted.experience : [])
                  .slice(0, 5)
                  .map((job, i) => {
                    const j = job as Record<string, unknown>;
                    return (
                      <div key={i} className="border-l-2 border-teal-200 pl-2">
                        <p className="text-sm font-medium text-gray-800">{String(j.title || j.position || j.role || "")}</p>
                        <p className="text-xs text-gray-500">
                          {String(j.company || j.employer || "")}
                          {(j.duration || j.dates) ? ` · ${String(j.duration || j.dates)}` : ""}
                        </p>
                        {j.description != null && <p className="text-xs text-gray-500 line-clamp-2">{String(j.description)}</p>}
                      </div>
                    );
                  })}
              </div>
            </div>
          )}
          {Array.isArray(extracted.skills) && (extracted.skills as string[]).length > 0 && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Skills</p>
              <div className="flex flex-wrap gap-1.5 mt-1">
                {(extracted.skills as string[]).slice(0, 30).map((s, i) => (
                  <span key={i} className="text-xs px-2 py-0.5 rounded-full border bg-teal-50 text-teal-700 border-teal-100">
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}
          {extracted.education != null && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Education</p>
              <ul className="space-y-1 mt-1">
                {(Array.isArray(extracted.education) ? extracted.education : [extracted.education]).slice(0, 5).map((item, i) => (
                  <li key={i} className="text-sm text-gray-600 flex gap-1.5">
                    <span className="text-teal-500 shrink-0">•</span>
                    <span>{typeof item === "string" ? item : JSON.stringify(item)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </>
  );
}

// ── Report Row ────────────────────────────────────────────────────────────────

function ReportRow({
  report,
  onPreview,
}: {
  report: MemberReport;
  onPreview: (id: number) => void;
}) {
  const ex = report.extracted as Record<string, unknown> | null;

  function renderList(items: unknown) {
    if (!Array.isArray(items) || items.length === 0) return <span className="text-gray-400">None</span>;
    return (
      <span className="text-gray-600">
        {(items as string[]).slice(0, 3).join(", ")}
        {items.length > 3 && ` +${items.length - 3} more`}
      </span>
    );
  }

  return (
    <button
      onClick={() => onPreview(report.id)}
      className="w-full text-left p-3 rounded-lg border border-gray-100 bg-white hover:bg-gray-50 transition-colors"
    >
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-base">📊</span>
        <span className="text-sm font-medium text-gray-800 truncate">{report.original_filename}</span>
        <span className="text-xs text-gray-400 ml-auto shrink-0">{formatShortDate(report.created_at)}</span>
      </div>
      {ex && (
        <div className="space-y-0.5 pl-6 text-xs">
          {ex.tasks_completed != null && (
            <p><span className="text-gray-400">Done:</span> {renderList(ex.tasks_completed)}</p>
          )}
          {ex.in_progress != null && (
            <p><span className="text-gray-400">In Progress:</span> {renderList(ex.in_progress)}</p>
          )}
          {ex.blockers != null && (
            <p><span className="text-gray-400">Blockers:</span> {renderList(ex.blockers)}</p>
          )}
        </div>
      )}
    </button>
  );
}

// ── Inline Document Preview Panel ─────────────────────────────────────────────

function DocPreviewPanel({ documentId, onClose }: { documentId: number; onClose: () => void }) {
  const { data: doc, isLoading } = useQuery({
    queryKey: ["document-detail", documentId],
    queryFn: () => getDocument(documentId),
  });

  const extracted = doc?.extracted_data?.[0]?.structured_data as Record<string, unknown> | undefined;

  function renderList(items: unknown) {
    if (!Array.isArray(items) || items.length === 0) return null;
    return (
      <ul className="space-y-1 mt-1">
        {(items as string[]).slice(0, 10).map((item, i) => (
          <li key={i} className="text-sm text-gray-600 flex gap-1.5">
            <span className="text-teal-500 shrink-0">•</span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <>
      <div className="fixed inset-0 bg-black/20 z-40" onClick={onClose} />
      <div className="fixed right-0 top-0 h-full w-[38%] bg-white z-50 shadow-xl flex flex-col overflow-y-auto">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 shrink-0">
          <div className="min-w-0 flex-1 mr-3">
            {isLoading ? (
              <div className="h-4 w-40 bg-gray-100 rounded animate-pulse" />
            ) : (
              <>
                <h2 className="text-base font-semibold text-gray-900 truncate">{doc?.original_filename ?? "Document"}</h2>
                <p className="text-xs text-gray-400 mt-0.5">{doc ? formatShortDate(doc.created_at) : ""}</p>
              </>
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {doc && (
              <a href={downloadDocument(doc.id)} target="_blank" rel="noopener noreferrer"
                className="text-xs px-3 py-1.5 rounded-md bg-teal-600 text-white hover:bg-teal-700 flex items-center gap-1">
                <Download className="w-3.5 h-3.5" /> Download
              </a>
            )}
            <button onClick={onClose} className="p-1.5 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600">✕</button>
          </div>
        </div>
        <div className="flex-1 px-5 py-4 space-y-4">
          {isLoading && <div className="flex items-center justify-center py-12"><Loader2 className="w-5 h-5 animate-spin text-teal-500" /></div>}
          {!isLoading && extracted && (
            <>
              {extracted.developer_name && <div><p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Developer</p><p className="text-sm text-gray-800">{String(extracted.developer_name)}</p></div>}
              {(extracted.week || extracted.date) && <div><p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Week / Date</p><p className="text-sm text-gray-700">{String(extracted.week || extracted.date)}</p></div>}
              {extracted.tasks_completed && <div><p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Tasks Completed</p>{renderList(extracted.tasks_completed)}</div>}
              {extracted.in_progress && <div><p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">In Progress</p>{renderList(extracted.in_progress)}</div>}
              {extracted.blockers && <div><p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Blockers</p>{renderList(extracted.blockers)}</div>}
              {extracted.hours_worked && <div><p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Hours Worked</p><p className="text-sm text-gray-700">{String(extracted.hours_worked)}</p></div>}
            </>
          )}
          {!isLoading && !extracted && <p className="text-sm text-gray-400 text-center py-8">No extracted content available.</p>}
        </div>
      </div>
    </>
  );
}

// ── Edit Dialog ───────────────────────────────────────────────────────────────

const LEVELS = ["junior", "mid", "senior", "lead"];

function EditDialog({
  member,
  open,
  onClose,
}: {
  member: { id: number; name: string; role: string; level?: string; start_date?: string; status: string; notes?: string };
  open: boolean;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    name: member.name,
    role: member.role,
    level: member.level ?? "",
    start_date: member.start_date ? member.start_date.split("T")[0] : "",
    status: member.status,
    notes: member.notes ?? "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleSave() {
    setError("");
    setSaving(true);
    try {
      await updateTeamMember(member.id, {
        name: form.name.trim() || undefined,
        role: form.role.trim() || undefined,
        level: form.level || undefined,
        start_date: form.start_date ? new Date(form.start_date).toISOString() : undefined,
        status: form.status,
        notes: form.notes.trim() || undefined,
      });
      qc.invalidateQueries({ queryKey: ["team-member", member.id] });
      qc.invalidateQueries({ queryKey: ["team"] });
      onClose();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Edit Team Member</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 mt-1">
          <div>
            <label className="text-xs font-medium text-gray-600 mb-1 block">Name *</label>
            <Input value={form.name} onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))} />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-600 mb-1 block">Role *</label>
            <Input value={form.role} onChange={(e) => setForm((p) => ({ ...p, role: e.target.value }))} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-gray-600 mb-1 block">Level</label>
              <Select value={form.level} onValueChange={(v) => setForm((p) => ({ ...p, level: v ?? "" }))}>
                <SelectTrigger><SelectValue placeholder="Select level" /></SelectTrigger>
                <SelectContent>
                  {LEVELS.map((l) => (
                    <SelectItem key={l} value={l}>{l.charAt(0).toUpperCase() + l.slice(1)}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 mb-1 block">Start Date</label>
              <Input type="date" value={form.start_date} onChange={(e) => setForm((p) => ({ ...p, start_date: e.target.value }))} />
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-gray-600 mb-1 block">Status</label>
            <Select value={form.status} onValueChange={(v) => setForm((p) => ({ ...p, status: v ?? "" }))}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="offboarded">Offboarded</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-xs font-medium text-gray-600 mb-1 block">Notes</label>
            <textarea
              className="w-full min-h-[80px] text-sm border border-gray-200 rounded-md px-3 py-2 resize-y focus:outline-none focus:ring-2 focus:ring-teal-400"
              value={form.notes}
              onChange={(e) => setForm((p) => ({ ...p, notes: e.target.value }))}
              placeholder="Internal notes about this team member…"
            />
          </div>
          {error && <p className="text-sm text-red-500">{error}</p>}
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button
              className="bg-teal-600 hover:bg-teal-700 text-white"
              disabled={saving || !form.name.trim() || !form.role.trim()}
              onClick={handleSave}
            >
              {saving ? <><Loader2 className="w-4 h-4 animate-spin mr-1" />Saving…</> : "Save Changes"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

const REPORTS_INITIAL = 3;

export default function TeamMemberDetail() {
  const params = useParams();
  const router = useRouter();
  const qc = useQueryClient();
  const memberId = Number(params.id);
  const resumeRef = useRef<HTMLInputElement>(null);

  const [editOpen, setEditOpen] = useState(false);
  const [previewDocId, setPreviewDocId] = useState<number | null>(null);
  const [showAllReports, setShowAllReports] = useState(false);
  const [uploadingResume, setUploadingResume] = useState(false);
  const [resumeError, setResumeError] = useState("");

  const { data: member, isLoading } = useQuery({
    queryKey: ["team-member", memberId],
    queryFn: () => getTeamMember(memberId),
    refetchInterval: (q) => {
      // poll while resume is being processed
      const m = q.state.data;
      if (!m?.resume_document_id) return false;
      return false; // ResumeContent handles its own polling
    },
  });

  const { data: reportsData } = useQuery({
    queryKey: ["team-member-reports", memberId],
    queryFn: () => getMemberReports(memberId),
  });

  const reports = reportsData?.items ?? [];

  const uploadResumeMut = useMutation({
    mutationFn: (file: File) => uploadTeamMemberResume(memberId, file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["team-member", memberId] });
      qc.invalidateQueries({ queryKey: ["document-detail"] });
    },
    onError: (e: unknown) => {
      setResumeError(e instanceof Error ? e.message : "Upload failed");
    },
  });

  const syncSkillsMut = useMutation({
    mutationFn: () => syncTeamMemberSkills(memberId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["team-member", memberId] }),
  });

  async function handleResumeUpload(file: File) {
    setResumeError("");
    setUploadingResume(true);
    try {
      await uploadResumeMut.mutateAsync(file);
    } finally {
      setUploadingResume(false);
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400">
        <Loader2 className="w-6 h-6 animate-spin" />
      </div>
    );
  }

  if (!member) {
    return (
      <div className="text-center py-16 text-gray-400">
        <p>Team member not found.</p>
        <button onClick={() => router.back()} className="text-teal-600 hover:underline text-sm mt-2">
          Go back
        </button>
      </div>
    );
  }

  const initials = member.name.split(" ").map((w: string) => w[0]).join("").slice(0, 2).toUpperCase();
  const visibleReports = showAllReports ? reports : reports.slice(0, REPORTS_INITIAL);

  return (
    <>
      {previewDocId !== null && (
        <DocPreviewPanel documentId={previewDocId} onClose={() => setPreviewDocId(null)} />
      )}
      <EditDialog member={member} open={editOpen} onClose={() => setEditOpen(false)} />
      <input
        ref={resumeRef}
        type="file"
        accept=".pdf,.doc,.docx,.txt"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleResumeUpload(file);
          e.target.value = "";
        }}
      />

      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => member?.project_id ? router.push(`/projects/${member.project_id}`) : router.back()}
          className="p-1.5 rounded-lg hover:bg-gray-200 text-gray-500"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <div className={`w-10 h-10 rounded-full font-semibold flex items-center justify-center text-sm shrink-0
            ${member.status === "offboarded" ? "bg-gray-100 text-gray-400" : "bg-teal-100 text-teal-700"}`}>
            {initials}
          </div>
          <div className="min-w-0">
            <h1 className="text-xl font-bold text-gray-900">{member.name}</h1>
            <p className="text-sm text-gray-500">{member.role}{member.level ? ` · ${member.level}` : ""}</p>
          </div>
          <Badge className={`ml-1 shrink-0 ${member.status === "active" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-gray-100 text-gray-500"}`}>
            {member.status === "active" ? "● Active" : "Offboarded"}
          </Badge>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="gap-1.5 shrink-0"
          onClick={() => setEditOpen(true)}
        >
          <Pencil className="w-3.5 h-3.5" /> Edit
        </Button>
      </div>

      {/* Hired-through-pipeline banner */}
      {member.hired_from_candidate_id && (
        <div className="mb-5 bg-teal-50 border border-teal-100 rounded-lg p-3 flex items-center gap-2 text-sm text-teal-700">
          <Users className="w-4 h-4 shrink-0" />
          <span>
            Hired through TalentLens pipeline.{" "}
            <button
              onClick={() => router.push(`/candidates/${member.hired_from_candidate_id}`)}
              className="font-medium text-teal-600 hover:underline"
            >
              View hiring history →
            </button>
          </span>
        </div>
      )}

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* LEFT: Resume */}
        <div className="lg:col-span-3 space-y-4">
          {/* Skills */}
          {member.skills && member.skills.length > 0 && (
            <Card className="border-gray-200">
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Skills</p>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 px-2 text-xs text-teal-600 hover:text-teal-700"
                    onClick={() => syncSkillsMut.mutate()}
                    disabled={syncSkillsMut.isPending}
                  >
                    {syncSkillsMut.isPending ? "Syncing…" : "Sync from Resume"}
                  </Button>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {member.skills.map((s) => (
                    <span key={s} className="text-xs px-2 py-0.5 rounded-full bg-teal-50 text-teal-700 border border-teal-100">
                      {s}
                    </span>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Resume section */}
          <Card className="border-gray-200">
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-3">
                <p className="text-sm font-semibold text-gray-800">Resume</p>
                {member.resume_document_id && (
                  <button
                    disabled={uploadingResume}
                    onClick={() => resumeRef.current?.click()}
                    className="text-xs px-2.5 py-1 rounded-md border border-gray-200 text-gray-600 hover:bg-gray-50 flex items-center gap-1"
                  >
                    {uploadingResume ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                    Replace
                  </button>
                )}
              </div>

              {resumeError && (
                <Alert className="mb-3 border-red-200 bg-red-50">
                  <AlertDescription className="text-red-700 text-xs">{resumeError}</AlertDescription>
                </Alert>
              )}

              {member.resume_document_id ? (
                <ResumeContent documentId={member.resume_document_id} />
              ) : (
                <div
                  className="border-2 border-dashed border-gray-200 rounded-xl p-8 text-center cursor-pointer hover:border-teal-400 hover:bg-teal-50 transition-colors"
                  onClick={() => resumeRef.current?.click()}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    const file = e.dataTransfer.files[0];
                    if (file) handleResumeUpload(file);
                  }}
                >
                  {uploadingResume ? (
                    <>
                      <Loader2 className="w-8 h-8 text-teal-400 mx-auto mb-2 animate-spin" />
                      <p className="text-sm text-gray-500">Uploading…</p>
                    </>
                  ) : (
                    <>
                      <FileText className="w-8 h-8 text-gray-300 mx-auto mb-2" />
                      <p className="text-sm font-medium text-gray-600">Drag & drop resume here</p>
                      <p className="text-xs text-gray-400 mt-1">or click to browse · PDF, DOC, DOCX, TXT</p>
                    </>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* RIGHT: Details + Reports */}
        <div className="lg:col-span-2 space-y-4">
          {/* Details */}
          <Card className="border-gray-200">
            <CardContent className="p-4">
              <p className="text-sm font-semibold text-gray-800 mb-3">Details</p>
              <div className="space-y-2 text-sm">
                {[
                  { label: "Role", value: member.role },
                  { label: "Level", value: member.level ?? "—" },
                  { label: "Start Date", value: formatDate(member.start_date) },
                  { label: "Status", value: member.status === "active" ? "● Active" : "Offboarded" },
                ].map(({ label, value }) => (
                  <div key={label} className="flex gap-2">
                    <span className="text-gray-400 w-20 shrink-0">{label}:</span>
                    <span className={`text-gray-800 ${label === "Status" && member.status === "active" ? "text-emerald-600" : ""}`}>
                      {value}
                    </span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Notes */}
          <NotesCard memberId={member.id} initialNotes={member.notes ?? ""} />

          {/* Weekly Reports */}
          <Card className="border-gray-200">
            <CardContent className="p-4">
              <p className="text-sm font-semibold text-gray-800 mb-3">
                Weekly Reports ({reports.length})
              </p>
              {reports.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-4">No reports linked yet.</p>
              ) : (
                <>
                  <div className="space-y-2">
                    {visibleReports.map((r) => (
                      <ReportRow key={r.id} report={r} onPreview={setPreviewDocId} />
                    ))}
                  </div>
                  {reports.length > REPORTS_INITIAL && (
                    <button
                      className="mt-3 text-xs text-teal-600 hover:text-teal-700 flex items-center gap-1 font-medium"
                      onClick={() => setShowAllReports((v) => !v)}
                    >
                      {showAllReports ? (
                        <><ChevronUp className="w-3.5 h-3.5" /> Show less</>
                      ) : (
                        <><ChevronDown className="w-3.5 h-3.5" /> Show all {reports.length} reports</>
                      )}
                    </button>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}

// ── Notes Card ────────────────────────────────────────────────────────────────

function NotesCard({ memberId, initialNotes }: { memberId: number; initialNotes: string }) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [notes, setNotes] = useState(initialNotes);
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      await updateTeamMember(memberId, { notes: notes.trim() || undefined });
      qc.invalidateQueries({ queryKey: ["team-member", memberId] });
    } finally {
      setSaving(false);
      setEditing(false);
    }
  }

  return (
    <Card className="border-gray-200">
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-2">
          <p className="text-sm font-semibold text-gray-800">Notes</p>
          {!editing && (
            <button
              onClick={() => setEditing(true)}
              className="text-xs text-gray-400 hover:text-teal-600 flex items-center gap-1"
            >
              <Pencil className="w-3 h-3" /> Edit
            </button>
          )}
        </div>
        {editing ? (
          <div className="space-y-2">
            <textarea
              className="w-full min-h-[80px] text-sm border border-gray-200 rounded-md px-3 py-2 resize-y focus:outline-none focus:ring-2 focus:ring-teal-400"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              autoFocus
            />
            <div className="flex gap-2 justify-end">
              <Button variant="outline" size="sm" onClick={() => { setEditing(false); setNotes(initialNotes); }}>
                Cancel
              </Button>
              <Button size="sm" className="bg-teal-600 hover:bg-teal-700 text-white" disabled={saving} onClick={save}>
                {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle className="w-3.5 h-3.5" />}
                Save
              </Button>
            </div>
          </div>
        ) : notes ? (
          <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{notes}</p>
        ) : (
          <p className="text-sm text-gray-400 italic">No notes yet. Click Edit to add.</p>
        )}
      </CardContent>
    </Card>
  );
}
