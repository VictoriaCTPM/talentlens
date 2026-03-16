"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Upload,
  FileText,
  Loader2,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  Trash2,
  Plus,
  Briefcase,
  UserRound,
  Users,
  Eye,
  Download,
} from "lucide-react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  getProject,
  getDocuments,
  uploadDocument,
  getJob,
  getAnalysisResults,
  getSufficiency,
  runTalentBrief,
  runHistoricalMatch,
  runLevelAdvisor,
  runCandidateScore,
  runJDRealityCheck,
  deleteDocument,
  getDocument,
  downloadDocument,
  getPositions,
  createPosition,
  deletePosition,
  getTeam,
  addTeamMember,
  deleteTeamMember,
  linkReportToMember,
  type Document,
  type AnalysisResult,
  type Position,
  type TeamMember,
} from "@/lib/api";
import { Input } from "@/components/ui/input";
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

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatBytes(n: number) {
  return n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1048576).toFixed(1)} MB`;
}

function DocTypeColor(t?: string) {
  const map: Record<string, string> = {
    resume: "bg-blue-100 text-blue-700",
    jd: "bg-teal-100 text-teal-700",
    job_request: "bg-teal-100 text-teal-700",
    report: "bg-purple-100 text-purple-700",
    client_report: "bg-purple-100 text-purple-700",
    interview: "bg-orange-100 text-orange-700",
  };
  return t ? map[t] ?? "bg-gray-100 text-gray-600" : "bg-gray-100 text-gray-500";
}

function StatusIcon({ status }: { status: string }) {
  if (status === "processed") return <CheckCircle className="w-4 h-4 text-emerald-500" />;
  if (status === "error") return <XCircle className="w-4 h-4 text-red-500" />;
  if (status === "processing" || status === "queued")
    return <Loader2 className="w-4 h-4 text-teal-500 animate-spin" />;
  return <Clock className="w-4 h-4 text-gray-400" />;
}

// ── Document Preview Sheet ─────────────────────────────────────────────────

function DocumentPreviewSheet({ documentId, onClose }: { documentId: number; onClose: () => void }) {
  const { data: doc, isLoading } = useQuery({
    queryKey: ["document-detail", documentId],
    queryFn: () => getDocument(documentId),
  });

  const extracted = doc?.extracted_data?.[0]?.structured_data as Record<string, unknown> | undefined;
  const docType = doc?.doc_type;

  function renderList(items: unknown, limit = 8) {
    if (!Array.isArray(items) || items.length === 0) return null;
    return (
      <ul className="space-y-1 mt-1">
        {items.slice(0, limit).map((item, i) => (
          <li key={i} className="text-sm text-gray-600 flex gap-1.5">
            <span className="text-teal-500 shrink-0">•</span>
            <span>{typeof item === "string" ? item : typeof item === "object" && item ? JSON.stringify(item) : String(item)}</span>
          </li>
        ))}
      </ul>
    );
  }

  function renderWorkHistory(history: unknown) {
    if (!Array.isArray(history) || history.length === 0) return null;
    return (
      <div className="space-y-2 mt-1">
        {history.slice(0, 5).map((job, i) => {
          const j = job as Record<string, unknown>;
          return (
            <div key={i} className="border-l-2 border-teal-200 pl-2">
              <p className="text-sm font-medium text-gray-800">{String(j.title || j.position || j.role || "")}</p>
              <p className="text-xs text-gray-500">{String(j.company || j.employer || "")} {j.duration || j.dates ? `· ${String(j.duration || j.dates || "")}` : ""}</p>
              {j.description ? <p className="text-xs text-gray-500 line-clamp-2">{String(j.description)}</p> : null}
            </div>
          );
        })}
      </div>
    );
  }

  function renderChips(items: unknown, colorClass = "bg-teal-50 text-teal-700 border-teal-100") {
    if (!Array.isArray(items) || items.length === 0) return null;
    return (
      <div className="flex flex-wrap gap-1.5 mt-1">
        {items.slice(0, 30).map((s, i) => (
          <span key={i} className={`text-xs px-2 py-0.5 rounded-full border ${colorClass}`}>
            {String(s)}
          </span>
        ))}
      </div>
    );
  }

  function renderContent() {
    if (!doc) return null;

    if (doc.status !== "processed") {
      return (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Loader2 className="w-8 h-8 animate-spin text-teal-400 mb-3" />
          <p className="text-sm text-gray-500">This document is still being processed…</p>
        </div>
      );
    }

    if (!extracted) {
      return <p className="text-sm text-gray-400 py-8 text-center">No extracted content available.</p>;
    }

    if (docType === "resume") {
      return (
        <>
          {extracted.summary && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Summary</p>
              <p className="text-sm text-gray-700 leading-relaxed">{String(extracted.summary)}</p>
            </div>
          )}
          {(extracted.work_history || extracted.experience) && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Experience</p>
              {renderWorkHistory(extracted.work_history || extracted.experience)}
            </div>
          )}
          {extracted.skills && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Skills</p>
              {renderChips(extracted.skills)}
            </div>
          )}
          {extracted.education && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Education</p>
              {renderList(extracted.education)}
            </div>
          )}
        </>
      );
    }

    if (docType === "jd" || docType === "job_request") {
      return (
        <>
          {extracted.title && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Title</p>
              <p className="text-sm font-medium text-gray-800">{String(extracted.title)}</p>
            </div>
          )}
          {extracted.level && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Level</p>
              <p className="text-sm text-gray-700">{String(extracted.level)}</p>
            </div>
          )}
          {extracted.required_skills && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Required Skills</p>
              {renderChips(extracted.required_skills)}
            </div>
          )}
          {extracted.nice_to_have_skills && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Nice to Have</p>
              {renderChips(extracted.nice_to_have_skills, "bg-gray-50 text-gray-600 border-gray-200")}
            </div>
          )}
          {extracted.responsibilities && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Responsibilities</p>
              {renderList(extracted.responsibilities)}
            </div>
          )}
          {extracted.requirements && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Requirements</p>
              {renderList(extracted.requirements)}
            </div>
          )}
        </>
      );
    }

    if (docType === "report" || docType === "client_report") {
      return (
        <>
          {extracted.developer_name && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Developer</p>
              <p className="text-sm text-gray-800">{String(extracted.developer_name)}</p>
            </div>
          )}
          {(extracted.week || extracted.date || extracted.week_start) && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Week / Date</p>
              <p className="text-sm text-gray-700">{String(extracted.week || extracted.date || extracted.week_start)}</p>
            </div>
          )}
          {extracted.tasks_completed && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Tasks Completed</p>
              {renderList(extracted.tasks_completed)}
            </div>
          )}
          {extracted.in_progress && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">In Progress</p>
              {renderList(extracted.in_progress)}
            </div>
          )}
          {extracted.blockers && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Blockers</p>
              {renderList(extracted.blockers)}
            </div>
          )}
          {extracted.hours_worked && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Hours Worked</p>
              <p className="text-sm text-gray-700">{String(extracted.hours_worked)}</p>
            </div>
          )}
        </>
      );
    }

    if (docType === "interview") {
      return (
        <>
          {extracted.candidate_name && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Candidate</p>
              <p className="text-sm text-gray-800">{String(extracted.candidate_name)}</p>
            </div>
          )}
          {extracted.position && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Position</p>
              <p className="text-sm text-gray-700">{String(extracted.position)}</p>
            </div>
          )}
          {extracted.date && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Date</p>
              <p className="text-sm text-gray-700">{String(extracted.date)}</p>
            </div>
          )}
          {(extracted.technical_score != null || extracted.communication_score != null) && (
            <div className="space-y-1">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Scores</p>
              {extracted.technical_score != null && (
                <p className="text-sm text-gray-700">Technical: <span className="font-medium">{String(extracted.technical_score)}/10</span></p>
              )}
              {extracted.communication_score != null && (
                <p className="text-sm text-gray-700">Communication: <span className="font-medium">{String(extracted.communication_score)}/10</span></p>
              )}
            </div>
          )}
          {extracted.verdict && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Verdict</p>
              <p className="text-sm font-medium text-gray-800">{String(extracted.verdict)}</p>
            </div>
          )}
          {extracted.strengths && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Strengths</p>
              {renderList(extracted.strengths)}
            </div>
          )}
          {extracted.weaknesses && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Weaknesses</p>
              {renderList(extracted.weaknesses)}
            </div>
          )}
          {extracted.notes && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Notes</p>
              <p className="text-sm text-gray-700 leading-relaxed">{String(extracted.notes)}</p>
            </div>
          )}
        </>
      );
    }

    // Fallback: show all extracted fields generically
    return (
      <div className="space-y-3">
        {Object.entries(extracted).map(([key, value]) => {
          if (value === null || value === undefined) return null;
          return (
            <div key={key}>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">{key.replace(/_/g, " ")}</p>
              {Array.isArray(value)
                ? renderList(value)
                : <p className="text-sm text-gray-700">{typeof value === "object" ? JSON.stringify(value, null, 2) : String(value)}</p>
              }
            </div>
          );
        })}
      </div>
    );
  }

  const statusLabel = !doc ? ""
    : doc.status === "processed" ? "✅ Processed"
    : doc.status === "processing" || doc.status === "queued" ? "⏳ Processing"
    : doc.status === "error" ? "❌ Error"
    : "⬜ Uploaded";

  return (
    <>
      <div className="fixed inset-0 bg-black/20 z-40" onClick={onClose} />
      <div className="fixed right-0 top-0 h-full w-[40%] bg-white z-50 shadow-xl overflow-y-auto flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 shrink-0">
          <div className="min-w-0 flex-1 mr-3">
            {isLoading ? (
              <div className="h-4 w-40 bg-gray-100 rounded animate-pulse" />
            ) : (
              <>
                <h2 className="text-base font-semibold text-gray-900 truncate">{doc?.original_filename ?? "Document"}</h2>
                <p className="text-xs text-gray-400 mt-0.5">
                  {doc?.doc_type && <span className={`inline-block px-1.5 py-0.5 rounded text-xs font-medium mr-1.5 ${DocTypeColor(doc.doc_type)}`}>{doc.doc_type}</span>}
                  {doc ? `${formatBytes(doc.file_size)} · Uploaded ${new Date(doc.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}` : ""}
                </p>
                <p className="text-xs text-gray-500 mt-0.5">{statusLabel}</p>
              </>
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {doc && (
              <a
                href={downloadDocument(doc.id)}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs px-3 py-1.5 rounded-md bg-teal-600 text-white hover:bg-teal-700 flex items-center gap-1"
              >
                <Download className="w-3.5 h-3.5" /> Download
              </a>
            )}
            <button onClick={onClose} className="p-1.5 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600">
              ✕
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          {isLoading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-5 h-5 animate-spin text-teal-500" />
            </div>
          )}
          {!isLoading && (
            <>
              {doc?.status === "error" && doc.error_message && (
                <Alert className="border-red-200 bg-red-50">
                  <AlertDescription className="text-red-700 text-sm">{doc.error_message}</AlertDescription>
                </Alert>
              )}
              <div className="space-y-5">
                {renderContent()}
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}

// ── Document Row ──────────────────────────────────────────────────────────────

function DocRow({
  doc,
  onDelete,
  onPreview,
}: {
  doc: Document;
  onDelete: (id: number) => void;
  onPreview: (id: number) => void;
}) {
  return (
    <div
      className="flex items-center gap-3 p-3 rounded-lg border border-gray-100 bg-white hover:bg-gray-50 cursor-pointer"
      onClick={() => onPreview(doc.id)}
    >
      <StatusIcon status={doc.status} />
      <FileText className="w-4 h-4 text-gray-400 shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-800 truncate">
          {doc.original_filename}
        </p>
        <p className="text-xs text-gray-400">
          {formatBytes(doc.file_size)} · {doc.file_type.toUpperCase()}
        </p>
      </div>
      {doc.doc_type && (
        <span
          className={`text-xs px-2 py-0.5 rounded-full font-medium ${DocTypeColor(doc.doc_type)}`}
        >
          {doc.doc_type}
        </span>
      )}
      {doc.status === "error" && doc.error_message && (
        <span className="text-xs text-red-500 max-w-[120px] truncate">
          {doc.error_message}
        </span>
      )}
      <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
        <button
          onClick={() => onPreview(doc.id)}
          className="p-1.5 rounded hover:bg-teal-50 text-gray-400 hover:text-teal-600 transition-colors"
          title="Preview"
        >
          <Eye className="w-3.5 h-3.5" />
        </button>
        <a
          href={downloadDocument(doc.id)}
          target="_blank"
          rel="noopener noreferrer"
          className="p-1.5 rounded hover:bg-blue-50 text-gray-400 hover:text-blue-600 transition-colors"
          title="Download"
        >
          <Download className="w-3.5 h-3.5" />
        </a>
        <button
          onClick={() => onDelete(doc.id)}
          className="p-1.5 rounded hover:bg-red-50 text-gray-400 hover:text-red-500 transition-colors"
          title="Delete"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}

// ── Documents Tab ─────────────────────────────────────────────────────────────

const DOC_CATEGORIES = [
  {
    key: "jd",
    label: "Job Description",
    icon: "📋",
    desc: "Client's job requirements. AI extracts skills and level, generates hiring recommendations.",
    hint: "Creates a position you can add candidates to.",
  },
  {
    key: "resume",
    label: "Resume / CV",
    icon: "📄",
    desc: "Candidate resume or CV. AI extracts skills and experience, scores against open positions.",
    hint: "Attach to a position to get AI scoring.",
  },
  {
    key: "report",
    label: "Weekly Report",
    icon: "📊",
    desc: "Weekly status updates or client-facing summaries. AI tracks team performance over time.",
    hint: null,
  },
  {
    key: "interview",
    label: "Interview Notes",
    icon: "🎤",
    desc: "Post-interview feedback and scorecards. AI learns what makes candidates succeed or fail.",
    hint: null,
  },
  {
    key: "other",
    label: "Other Document",
    icon: "📁",
    desc: "Any other project-related file (SOW, org chart, process doc). AI indexes it for context.",
    hint: null,
  },
] as const;

function DocumentsTab({ projectId }: { projectId: number }) {
  const qc = useQueryClient();
  const [createFromDocId, setCreateFromDocId] = useState<number | undefined>();
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [uploading, setUploading] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState("");
  const [previewDocId, setPreviewDocId] = useState<number | null>(null);
  const fileRefs = useRef<Record<string, HTMLInputElement | null>>({});

  const { data, refetch } = useQuery({
    queryKey: ["documents", projectId],
    queryFn: () => getDocuments(projectId),
    refetchInterval: (query) => {
      const docs = query.state.data?.items ?? [];
      const busy = docs.some((d) => d.status === "queued" || d.status === "processing");
      return busy ? 2000 : false;
    },
  });

  const { data: positionsData } = useQuery({
    queryKey: ["positions", projectId],
    queryFn: () => getPositions(projectId),
  });

  const { data: teamData } = useQuery({
    queryKey: ["team", projectId],
    queryFn: () => getTeam(projectId),
  });
  const teamMembers = teamData?.items ?? [];

  const docs = data?.items ?? [];
  const linkedJdIds = new Set(
    (positionsData?.items ?? []).map((p) => p.jd_document_id).filter(Boolean)
  );

  const deleteMut = useMutation({
    mutationFn: (id: number) => deleteDocument(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents", projectId] }),
  });

  const linkReportMut = useMutation({
    mutationFn: ({ memberId, docId }: { memberId: number; docId: number }) =>
      linkReportToMember(memberId, docId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["documents", projectId] });
      qc.invalidateQueries({ queryKey: ["team", projectId] });
    },
  });

  async function handleUpload(file: File, docType: string) {
    setUploading(docType);
    setUploadError("");
    try {
      await uploadDocument(projectId, file, docType === "other" ? undefined : docType);
      refetch();
    } catch (e: unknown) {
      setUploadError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(null);
    }
  }

  // Group docs by type (with fallback bucket)
  const byType = docs.reduce<Record<string, Document[]>>((acc, d) => {
    const key = d.doc_type ?? "other";
    if (!acc[key]) acc[key] = [];
    acc[key].push(d);
    return acc;
  }, {});

  return (
    <div>
      {previewDocId !== null && (
        <DocumentPreviewSheet documentId={previewDocId} onClose={() => setPreviewDocId(null)} />
      )}
      {/* Categorized upload sections */}
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Upload Documents</h3>
        <p className="text-xs text-gray-500 mb-4">Choose a document type so AI can process it correctly.</p>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {DOC_CATEGORIES.map((cat) => {
            const catDocs = byType[cat.key] ?? [];
            return (
              <div key={cat.key} className="bg-white border border-gray-200 rounded-xl p-4">
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div>
                    <div className="flex items-center gap-1.5">
                      <span className="text-base">{cat.icon}</span>
                      <span className="text-sm font-semibold text-gray-800">{cat.label}</span>
                      {catDocs.length > 0 && (
                        <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded-full">{catDocs.length}</span>
                      )}
                    </div>
                    <p className="text-xs text-gray-500 mt-1">{cat.desc}</p>
                    {cat.hint && <p className="text-xs text-teal-600 mt-0.5">→ {cat.hint}</p>}
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  className="w-full text-xs mt-1 border-teal-200 text-teal-700 hover:bg-teal-50"
                  disabled={uploading === cat.key}
                  onClick={() => fileRefs.current[cat.key]?.click()}
                >
                  {uploading === cat.key ? (
                    <><Loader2 className="w-3 h-3 animate-spin mr-1" />Uploading…</>
                  ) : (
                    <><Upload className="w-3 h-3 mr-1" />Upload {cat.label}</>
                  )}
                </Button>
                <input
                  ref={(el) => { fileRefs.current[cat.key] = el; }}
                  type="file"
                  accept=".pdf,.doc,.docx,.txt"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) handleUpload(file, cat.key);
                    e.target.value = "";
                  }}
                />
              </div>
            );
          })}
        </div>
        {uploadError && (
          <Alert className="mt-3 border-red-200 bg-red-50">
            <AlertDescription className="text-red-700 text-sm">{uploadError}</AlertDescription>
          </Alert>
        )}
      </div>

      {/* Uploaded documents grouped by type */}
      {docs.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-700 mb-3">
            Uploaded Documents ({docs.length})
          </h3>
          {DOC_CATEGORIES.map((cat) => {
            const catDocs = byType[cat.key] ?? [];
            if (catDocs.length === 0) return null;
            return (
              <div key={cat.key} className="mb-4">
                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <span>{cat.icon}</span> {cat.label}s ({catDocs.length})
                </h4>
                <div className="space-y-1.5">
                  {catDocs.map((doc) => (
                    <div key={doc.id}>
                      <DocRow doc={doc} onDelete={(id) => deleteMut.mutate(id)} onPreview={setPreviewDocId} />
                      {(doc.doc_type === "jd" || doc.doc_type === "job_request") &&
                        doc.status === "processed" &&
                        !linkedJdIds.has(doc.id) && (
                        <div className="mt-1 mb-1 ml-8 flex items-center gap-2 text-xs text-amber-600">
                          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                          <span>Not linked to any position.</span>
                          <button
                            className="font-medium underline hover:text-amber-700"
                            onClick={() => { setCreateFromDocId(doc.id); setCreateDialogOpen(true); }}
                          >
                            Create Position
                          </button>
                        </div>
                      )}
                      {(doc.doc_type === "report" || doc.doc_type === "client_report") &&
                        doc.status === "processed" && (
                        <div className="mt-1 mb-1 ml-8 text-xs">
                          {doc.team_member_id ? (
                            <span className="flex items-center gap-1 text-gray-500">
                              <span className="text-emerald-500">→</span>
                              Linked to:{" "}
                              <span className="font-medium text-gray-700">
                                {teamMembers.find((m) => m.id === doc.team_member_id)?.name ?? `Member #${doc.team_member_id}`}
                              </span>
                              {teamMembers.find((m) => m.id === doc.team_member_id)?.role && (
                                <span className="text-gray-400">({teamMembers.find((m) => m.id === doc.team_member_id)?.role})</span>
                              )}
                            </span>
                          ) : (
                            <div className="flex items-center gap-2 text-amber-600">
                              <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                              {doc.developer_name_hint ? (
                                <span>Developer: &quot;{doc.developer_name_hint}&quot; — not linked to team member.</span>
                              ) : (
                                <span>Not linked to a team member.</span>
                              )}
                              {teamMembers.length > 0 && (
                                <select
                                  className="ml-1 text-xs border border-amber-300 rounded px-1 py-0.5 bg-white text-gray-700 cursor-pointer"
                                  defaultValue=""
                                  onChange={(e) => {
                                    if (e.target.value) {
                                      linkReportMut.mutate({ memberId: Number(e.target.value), docId: doc.id });
                                      e.target.value = "";
                                    }
                                  }}
                                >
                                  <option value="">Link to…</option>
                                  {teamMembers
                                    .filter((m) => m.status === "active")
                                    .map((m) => (
                                      <option key={m.id} value={m.id}>{m.name}</option>
                                    ))}
                                </select>
                              )}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
          {/* Show unclassified docs if any */}
          {Object.entries(byType)
            .filter(([key]) => !DOC_CATEGORIES.map(c => c.key).includes(key as never))
            .map(([type, typeDocs]) => (
              <div key={type} className="mb-4">
                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                  {type} ({typeDocs.length})
                </h4>
                <div className="space-y-1.5">
                  {typeDocs.map((doc) => (
                    <DocRow key={doc.id} doc={doc} onDelete={(id) => deleteMut.mutate(id)} onPreview={setPreviewDocId} />
                  ))}
                </div>
              </div>
            ))}
        </div>
      )}

      <NewPositionDialog
        projectId={projectId}
        open={createDialogOpen}
        onClose={() => { setCreateDialogOpen(false); setCreateFromDocId(undefined); }}
        prefillDocId={createFromDocId}
      />
    </div>
  );
}

// ── Analysis Mode Card ────────────────────────────────────────────────────────

const MODE_META = {
  A: { label: "Talent Brief", color: "bg-teal-100 text-teal-700", desc: "Skills, search tips, historical insights from your JDs" },
  B: { label: "Historical Match", color: "bg-blue-100 text-blue-700", desc: "Similar past positions, success & failure patterns" },
  C: { label: "Level Advisor", color: "bg-purple-100 text-purple-700", desc: "Recommended seniority level with historical evidence" },
  D: { label: "Candidate Scorer", color: "bg-orange-100 text-orange-700", desc: "Score a resume against a JD (0–100) with breakdown" },
  E: { label: "JD Reality Check", color: "bg-rose-100 text-rose-700", desc: "Audit a JD against your team and reports — is this hire actually needed?" },
};

function AnalysisModeCard({
  mode,
  projectId,
  documents,
  existingResults,
  onRun,
}: {
  mode: "A" | "B" | "C" | "D" | "E";
  projectId: number;
  documents: Document[];
  existingResults: AnalysisResult[];
  onRun: () => void;
}) {
  const meta = MODE_META[mode];
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [selectedJd, setSelectedJd] = useState<number | "">("");
  const [selectedResume, setSelectedResume] = useState<number | "">("");

  const { data: sufficiency } = useQuery({
    queryKey: ["sufficiency", projectId, mode],
    queryFn: () => getSufficiency(projectId, mode),
  });

  const jds = documents.filter((d) => ["jd", "job_request"].includes(d.doc_type ?? "") && d.status === "processed");
  const resumes = documents.filter((d) => d.doc_type === "resume" && d.status === "processed");

  const latestResult = existingResults
    .filter((r) => r.analysis_mode === mode)
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0];

  async function run() {
    setRunning(true);
    setError("");
    try {
      if (mode === "A") await runTalentBrief(Number(selectedJd || jds[0]?.id));
      else if (mode === "B") await runHistoricalMatch(Number(selectedJd || jds[0]?.id));
      else if (mode === "C") await runLevelAdvisor(Number(selectedJd || jds[0]?.id));
      else if (mode === "D") await runCandidateScore(Number(selectedResume), Number(selectedJd));
      else if (mode === "E") await runJDRealityCheck(Number(selectedJd || jds[0]?.id));
      onRun();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setRunning(false);
    }
  }

  const canRun = sufficiency?.can_run &&
    (mode === "D" ? selectedJd && selectedResume : (selectedJd || jds.length > 0));

  return (
    <Card className="bg-white border border-gray-200">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${meta.color}`}>
            Mode {mode}
          </span>
          <CardTitle className="text-[15px]">{meta.label}</CardTitle>
        </div>
        <p className="text-sm text-gray-500 mt-1">{meta.desc}</p>
      </CardHeader>
      <CardContent className="space-y-3">
        {sufficiency && !sufficiency.can_run && (
          <Alert className="border-amber-200 bg-amber-50 py-2">
            <AlertTriangle className="w-4 h-4 text-amber-500" />
            <AlertDescription className="text-amber-700 text-xs ml-1">
              {sufficiency.missing.join(" · ")}
            </AlertDescription>
          </Alert>
        )}

        {/* JD selector (modes A/B/C/D) */}
        {jds.length > 0 && (
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Job Description</label>
            <select
              className="w-full text-sm border border-gray-200 rounded-md px-2 py-1.5 bg-white"
              value={selectedJd}
              onChange={(e) => setSelectedJd(Number(e.target.value))}
            >
              <option value="">Select JD…</option>
              {jds.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.original_filename}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Resume selector (mode D only) */}
        {mode === "D" && resumes.length > 0 && (
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Resume</label>
            <select
              className="w-full text-sm border border-gray-200 rounded-md px-2 py-1.5 bg-white"
              value={selectedResume}
              onChange={(e) => setSelectedResume(Number(e.target.value))}
            >
              <option value="">Select Resume…</option>
              {resumes.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.original_filename}
                </option>
              ))}
            </select>
          </div>
        )}

        {error && <p className="text-xs text-red-500">{error}</p>}

        <Button
          size="sm"
          className="w-full bg-teal-600 hover:bg-teal-700 text-white"
          disabled={!canRun || running}
          onClick={run}
        >
          {running ? (
            <><Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> Running…</>
          ) : latestResult ? "Re-run Analysis" : "Run Analysis"}
        </Button>

        {/* Latest result preview */}
        {latestResult && (
          <ResultPreview mode={mode} result={latestResult} />
        )}
      </CardContent>
    </Card>
  );
}

// ── Result Preview ────────────────────────────────────────────────────────────

function ResultPreview({ mode, result }: { mode: string; result: AnalysisResult }) {
  const d = result.result_data as Record<string, unknown>;
  const conf = (result.confidence_score ?? 0) * 100;

  return (
    <div className="border-t border-gray-100 pt-3 space-y-2">
      {/* Confidence bar */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-500 shrink-0">Confidence</span>
        <Progress value={conf} className="h-1.5 flex-1" />
        <span className="text-xs font-medium text-gray-700">{Math.round(conf)}%</span>
      </div>

      {mode === "A" && <TalentBriefPreview d={d} />}
      {mode === "B" && <HistoricalMatchPreview d={d} />}
      {mode === "C" && <LevelAdvisorPreview d={d} />}
      {mode === "D" && <CandidateScorePreview d={d} />}
      {mode === "E" && <JDRealityCheckPreview d={d} />}

      {/* Sources */}
      {Array.isArray(d.sources) && (d.sources as string[]).length > 0 && (
        <div className="text-xs text-gray-400 border-t border-gray-50 pt-2">
          <span className="font-medium">Sources: </span>
          {(d.sources as string[]).slice(0, 3).join(" · ")}
        </div>
      )}
    </div>
  );
}

function TalentBriefPreview({ d }: { d: Record<string, unknown> }) {
  const skills = d.skills_required as Array<{ name: string; criticality: string }> ?? [];
  return (
    <div className="space-y-2">
      {skills.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-600 mb-1">Required Skills</p>
          <div className="flex flex-wrap gap-1">
            {skills.slice(0, 6).map((s, i) => (
              <span key={i} className={`text-xs px-1.5 py-0.5 rounded-full ${s.criticality === "must" ? "bg-teal-100 text-teal-700" : "bg-gray-100 text-gray-600"}`}>
                {s.name}
              </span>
            ))}
          </div>
        </div>
      )}
      {d.estimated_time_to_fill_days != null && (
        <p className="text-xs text-gray-500">
          <span className="font-medium">Estimated time to fill:</span>{" "}
          {String(d.estimated_time_to_fill_days)} days
        </p>
      )}
      {Array.isArray(d.pitfalls) && (d.pitfalls as string[]).length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-600 mb-1">Pitfalls</p>
          {(d.pitfalls as string[]).slice(0, 2).map((p, i) => (
            <p key={i} className="text-xs text-gray-500">• {p}</p>
          ))}
        </div>
      )}
    </div>
  );
}

function HistoricalMatchPreview({ d }: { d: Record<string, unknown> }) {
  const patterns = d.success_patterns as string[] ?? [];
  const failures = d.failure_patterns as string[] ?? [];
  return (
    <div className="space-y-2">
      {patterns.length > 0 && (
        <div>
          <p className="text-xs font-medium text-emerald-700 mb-1">✓ Success Patterns</p>
          {patterns.slice(0, 2).map((p, i) => <p key={i} className="text-xs text-gray-500">• {p}</p>)}
        </div>
      )}
      {failures.length > 0 && (
        <div>
          <p className="text-xs font-medium text-red-600 mb-1">✗ Failure Patterns</p>
          {failures.slice(0, 2).map((f, i) => <p key={i} className="text-xs text-gray-500">• {f}</p>)}
        </div>
      )}
    </div>
  );
}

function LevelAdvisorPreview({ d }: { d: Record<string, unknown> }) {
  const levelColor: Record<string, string> = {
    junior: "bg-gray-100 text-gray-600",
    mid: "bg-blue-100 text-blue-700",
    senior: "bg-teal-100 text-teal-700",
    lead: "bg-purple-100 text-purple-700",
  };
  const level = d.recommended_level as string ?? "";
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-gray-600">Recommended Level:</span>
        <span className={`text-xs font-bold px-2 py-0.5 rounded-full capitalize ${levelColor[level] ?? "bg-gray-100 text-gray-600"}`}>
          {level}
        </span>
      </div>
      {d.reasoning != null && (
        <p className="text-xs text-gray-500 line-clamp-3">{String(d.reasoning)}</p>
      )}
    </div>
  );
}

function CandidateScorePreview({ d }: { d: Record<string, unknown> }) {
  const score = d.overall_score as number ?? 0;
  const verdict = d.verdict as string ?? "";
  const verdictColor: Record<string, string> = {
    strong_fit: "bg-emerald-100 text-emerald-700",
    moderate_fit: "bg-blue-100 text-blue-700",
    risky: "bg-amber-100 text-amber-700",
    not_recommended: "bg-red-100 text-red-700",
  };
  const sm = d.skill_match as Record<string, unknown> ?? {};
  const em = d.experience_match as Record<string, unknown> ?? {};
  const tm = d.team_compatibility as Record<string, unknown> ?? {};

  return (
    <div className="space-y-3">
      {/* Score circle + verdict */}
      <div className="flex items-center gap-3">
        <div className={`w-12 h-12 rounded-full flex items-center justify-center text-lg font-bold ${score >= 85 ? "bg-emerald-100 text-emerald-700" : score >= 65 ? "bg-blue-100 text-blue-700" : score >= 45 ? "bg-amber-100 text-amber-700" : "bg-red-100 text-red-700"}`}>
          {score}
        </div>
        <div>
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${verdictColor[verdict] ?? "bg-gray-100 text-gray-600"}`}>
            {verdict?.replace(/_/g, " ")}
          </span>
        </div>
      </div>

      {/* Breakdown bars */}
      {[
        { label: "Skills", val: sm.score as number ?? 0 },
        { label: "Experience", val: em.score as number ?? 0 },
        { label: "Team Fit", val: tm.score as number ?? 0 },
      ].map(({ label, val }) => (
        <div key={label} className="flex items-center gap-2">
          <span className="text-xs text-gray-500 w-20 shrink-0">{label}</span>
          <Progress value={val} className="h-1.5 flex-1" />
          <span className="text-xs font-medium text-gray-700 w-8 text-right">{val}</span>
        </div>
      ))}

      {/* Strengths / Gaps */}
      <div className="flex flex-wrap gap-1">
        {(d.strengths as string[] ?? []).slice(0, 3).map((s, i) => (
          <span key={i} className="text-xs bg-emerald-50 text-emerald-700 px-1.5 py-0.5 rounded-full">
            {s}
          </span>
        ))}
        {(d.gaps as string[] ?? []).slice(0, 2).map((g, i) => (
          <span key={i} className="text-xs bg-red-50 text-red-600 px-1.5 py-0.5 rounded-full">
            {g}
          </span>
        ))}
      </div>

      {/* Team Complementarity */}
      {d.team_complementarity != null && (() => {
        const tc = d.team_complementarity as Record<string, unknown>;
        const fills = tc.fills_gaps as string[] ?? [];
        const overlaps = tc.overlaps as string[] ?? [];
        if (fills.length === 0 && overlaps.length === 0 && !tc.recommendation) return null;
        return (
          <div className="border-t border-gray-100 pt-2 space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-gray-600">Team Complementarity</span>
              {tc.score != null && (
                <span className={`text-xs font-medium ${Number(tc.score) >= 70 ? "text-emerald-600" : Number(tc.score) >= 50 ? "text-amber-600" : "text-red-500"}`}>
                  {String(tc.score)}
                </span>
              )}
            </div>
            {fills.length > 0 && (
              <div className="flex flex-wrap gap-1">
                <span className="text-xs text-gray-400 mr-0.5">Fills gaps:</span>
                {fills.slice(0, 4).map((f, i) => (
                  <span key={i} className="text-xs bg-teal-50 text-teal-700 px-1.5 py-0.5 rounded-full">{f}</span>
                ))}
              </div>
            )}
            {overlaps.length > 0 && (
              <div className="flex flex-wrap gap-1">
                <span className="text-xs text-gray-400 mr-0.5">Overlaps:</span>
                {overlaps.slice(0, 3).map((o, i) => (
                  <span key={i} className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded-full">{o}</span>
                ))}
              </div>
            )}
            {tc.recommendation != null && (
              <p className="text-xs text-gray-500 italic line-clamp-2">{String(tc.recommendation)}</p>
            )}
          </div>
        );
      })()}
    </div>
  );
}

// ── JD Reality Check Preview ──────────────────────────────────────────────────

function JDRealityCheckPreview({ d }: { d: Record<string, unknown> }) {
  const nc = d.necessity_check as Record<string, unknown> ?? {};
  const svr = d.skills_vs_reality as Record<string, unknown> ?? {};
  const wa = d.workload_analysis as Record<string, unknown> ?? {};
  const isJustified = nc.is_hire_justified !== false;
  const priority = nc.priority as string ?? "medium";

  const jdRequires = svr.jd_requires as string[] ?? [];
  const alreadyHas = new Set((svr.team_already_has as string[] ?? []).map((s) => s.toLowerCase()));
  const questionable = new Set((svr.questionable_requirements as string[] ?? []).map((s) => s.toLowerCase()));
  const actuallyNeeded = svr.actually_needed as string[] ?? [];
  const suggestions = d.jd_improvement_suggestions as string[] ?? [];

  return (
    <div className="space-y-3">
      {/* Verdict badges */}
      <div className="flex flex-wrap gap-1.5">
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${isJustified ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}>
          {isJustified ? "Hire Justified" : "Hire Questioned"}
        </span>
        <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${
          priority === "critical" ? "bg-red-50 text-red-600" :
          priority === "high" ? "bg-orange-50 text-orange-600" :
          priority === "low" ? "bg-gray-100 text-gray-500" :
          "bg-blue-50 text-blue-600"
        }`}>
          {priority} priority
        </span>
      </div>

      {/* Reasoning quote */}
      {d.reasoning != null && (
        <blockquote className="border-l-2 border-rose-300 pl-2 text-xs text-gray-600 italic line-clamp-3">
          {String(d.reasoning)}
        </blockquote>
      )}

      {/* Skills vs Reality table */}
      {jdRequires.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-600 mb-1">Skills vs Reality</p>
          <div className="space-y-0.5">
            {jdRequires.slice(0, 5).map((skill, i) => {
              const lower = skill.toLowerCase();
              const has = alreadyHas.has(lower) || [...alreadyHas].some((h) => lower.includes(h) || h.includes(lower));
              const odd = questionable.has(lower) || [...questionable].some((q) => lower.includes(q) || q.includes(lower));
              return (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <span className={`shrink-0 ${has ? "text-emerald-500" : odd ? "text-amber-500" : "text-gray-400"}`}>
                    {has ? "✅" : odd ? "⚠️" : "•"}
                  </span>
                  <span className="text-gray-700 truncate">{skill}</span>
                  {has && <span className="text-gray-400 text-[10px] ml-auto shrink-0">team has</span>}
                  {odd && !has && <span className="text-amber-500 text-[10px] ml-auto shrink-0">questionable</span>}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Actually needed */}
      {actuallyNeeded.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-600 mb-1">Actually Needed</p>
          <div className="flex flex-wrap gap-1">
            {actuallyNeeded.slice(0, 5).map((s, i) => (
              <span key={i} className="text-xs bg-rose-50 text-rose-700 px-1.5 py-0.5 rounded-full">{s}</span>
            ))}
          </div>
        </div>
      )}

      {/* Workload mismatch */}
      {Array.isArray(wa.mismatches) && (wa.mismatches as string[]).length > 0 && (
        <div>
          <p className="text-xs font-medium text-amber-700 mb-1">⚠️ JD vs Reality mismatches</p>
          {(wa.mismatches as string[]).slice(0, 2).map((m, i) => (
            <p key={i} className="text-xs text-gray-500">• {m}</p>
          ))}
        </div>
      )}

      {/* Suggestions */}
      {suggestions.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-600 mb-1">JD Improvements</p>
          {suggestions.slice(0, 3).map((s, i) => (
            <p key={i} className="text-xs text-gray-500">• {s}</p>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Positions Tab ─────────────────────────────────────────────────────────────

function NewPositionDialog({
  projectId,
  jdDocs,
  open,
  onClose,
  prefillDocId,
}: {
  projectId: number;
  jdDocs?: Document[];
  open: boolean;
  onClose: () => void;
  prefillDocId?: number;
}) {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [title, setTitle] = useState("");
  const [jdDocId, setJdDocId] = useState<number | undefined>(prefillDocId);
  const [level, setLevel] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [jdMode, setJdMode] = useState<"upload" | "existing">(prefillDocId ? "existing" : "upload");
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Reset when dialog opens/closes
  useEffect(() => {
    if (open) {
      setJdDocId(prefillDocId);
      setJdMode(prefillDocId ? "existing" : "upload");
      setTitle(""); setLevel(""); setFile(null); setSearch(""); setError("");
    }
  }, [open, prefillDocId]);

  const safeJdDocs = jdDocs ?? [];
  const filteredDocs = safeJdDocs.filter((d) =>
    d.original_filename.toLowerCase().includes(search.toLowerCase())
  );

  async function handleSubmit() {
    setError("");
    if (jdMode === "upload" && !file) {
      setError("Please upload a JD file or switch to 'Choose existing'.");
      return;
    }
    setLoading(true);
    try {
      await createPosition({
        title: title || undefined,
        project_id: projectId,
        jd_document_id: jdMode === "existing" ? jdDocId : undefined,
        level: level || undefined,
        file: jdMode === "upload" && file ? file : undefined,
      });
      qc.invalidateQueries({ queryKey: ["positions", projectId] });
      qc.invalidateQueries({ queryKey: ["documents", projectId] });
      onClose();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create position");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Create New Position</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          {/* Title */}
          <div>
            <label className="text-sm font-medium text-gray-700">
              Position Title <span className="text-gray-400 font-normal">(optional — extracted from JD)</span>
            </label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Senior Backend Engineer"
              className="mt-1"
            />
          </div>

          {/* JD section */}
          <div>
            <label className="text-sm font-medium text-gray-700 block mb-2">
              Job Description <span className="text-red-400">*</span>
            </label>

            {/* Mode tabs */}
            <div className="flex gap-1 mb-3 p-1 bg-gray-100 rounded-lg w-fit">
              <button
                onClick={() => setJdMode("upload")}
                className={`text-xs px-3 py-1.5 rounded-md font-medium transition-colors ${
                  jdMode === "upload" ? "bg-white shadow-sm text-gray-900" : "text-gray-500 hover:text-gray-700"
                }`}
              >
                Upload new JD
              </button>
              <button
                onClick={() => setJdMode("existing")}
                className={`text-xs px-3 py-1.5 rounded-md font-medium transition-colors ${
                  jdMode === "existing" ? "bg-white shadow-sm text-gray-900" : "text-gray-500 hover:text-gray-700"
                }`}
              >
                Choose uploaded ({safeJdDocs.length})
              </button>
            </div>

            {jdMode === "upload" ? (
              <div
                className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${
                  file ? "border-teal-400 bg-teal-50" : "border-gray-300 hover:border-teal-400 hover:bg-gray-50"
                }`}
                onClick={() => fileRef.current?.click()}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  const dropped = e.dataTransfer.files[0];
                  if (dropped) setFile(dropped);
                }}
              >
                {file ? (
                  <div className="flex items-center justify-center gap-2">
                    <CheckCircle className="w-5 h-5 text-teal-500" />
                    <span className="text-sm font-medium text-teal-700">{file.name}</span>
                    <button
                      className="text-xs text-gray-400 hover:text-red-500 ml-2"
                      onClick={(e) => { e.stopPropagation(); setFile(null); }}
                    >
                      ✕
                    </button>
                  </div>
                ) : (
                  <>
                    <Upload className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                    <p className="text-sm text-gray-600 font-medium">Drag & drop JD file here</p>
                    <p className="text-xs text-gray-400 mt-1">or click to browse · PDF, DOC, DOCX, TXT (max 10MB)</p>
                  </>
                )}
                <input
                  ref={fileRef}
                  type="file"
                  accept=".pdf,.doc,.docx,.txt"
                  className="hidden"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
              </div>
            ) : (
              <div className="border border-gray-200 rounded-xl overflow-hidden">
                <div className="p-2 border-b border-gray-100">
                  <Input
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="🔍 Search uploaded JDs…"
                    className="border-0 shadow-none focus-visible:ring-0 text-sm"
                  />
                </div>
                <div className="max-h-44 overflow-y-auto">
                  {filteredDocs.length === 0 ? (
                    <p className="text-xs text-gray-400 text-center py-4">
                      {safeJdDocs.length === 0 ? "No JD documents uploaded yet" : "No matches"}
                    </p>
                  ) : (
                    filteredDocs.map((d) => (
                      <button
                        key={d.id}
                        onClick={() => {
                          setJdDocId(d.id);
                          if (!title) setTitle(d.original_filename.replace(/\.(pdf|docx?|txt)$/i, ""));
                        }}
                        className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50 flex items-center gap-2 transition-colors ${
                          jdDocId === d.id ? "bg-teal-50 text-teal-700" : "text-gray-700"
                        }`}
                      >
                        {jdDocId === d.id ? (
                          <CheckCircle className="w-3.5 h-3.5 text-teal-500 shrink-0" />
                        ) : (
                          <FileText className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                        )}
                        <span className="truncate">{d.original_filename}</span>
                        <span className="text-xs text-gray-400 ml-auto shrink-0">{d.doc_type}</span>
                      </button>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Level */}
          <div>
            <label className="text-sm font-medium text-gray-700">
              Level <span className="text-gray-400 font-normal">(optional, AI will recommend)</span>
            </label>
            <div className="flex gap-2 mt-1">
              {["junior", "mid", "senior", "lead"].map((l) => (
                <button
                  key={l}
                  onClick={() => setLevel(level === l ? "" : l)}
                  className={`text-xs px-3 py-1.5 rounded-full border font-medium capitalize transition-colors ${
                    level === l
                      ? "bg-teal-600 text-white border-teal-600"
                      : "bg-white text-gray-600 border-gray-200 hover:border-teal-400"
                  }`}
                >
                  {l}
                </button>
              ))}
            </div>
          </div>

          {error && <p className="text-sm text-red-500">{error}</p>}

          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button
              className="bg-teal-600 hover:bg-teal-700 text-white"
              disabled={loading || (jdMode === "existing" && !jdDocId)}
              onClick={handleSubmit}
            >
              {loading ? <><Loader2 className="w-4 h-4 animate-spin mr-1" />Creating…</> : "Create Position"}
            </Button>
          </div>

          <p className="text-xs text-gray-400 text-center border-t border-gray-100 pt-3">
            After creation, AI will analyze the JD and provide hiring recommendations.
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function PositionStatusDot({ status }: { status: string }) {
  const colors: Record<string, string> = {
    open: "bg-emerald-500",
    paused: "bg-amber-400",
    closed: "bg-gray-400",
    filled: "bg-blue-500",
  };
  return <span className={`w-2 h-2 rounded-full shrink-0 ${colors[status] ?? "bg-gray-400"}`} />;
}

function PositionsTab({ projectId }: { projectId: number }) {
  const [newOpen, setNewOpen] = useState(false);
  const [prefillDocId, setPrefillDocId] = useState<number | undefined>();
  const qc = useQueryClient();

  const { data: posData } = useQuery({
    queryKey: ["positions", projectId],
    queryFn: () => getPositions(projectId),
    // Poll while any JD is still processing
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      return items.some((p) => p.jd_processing_status === "queued" || p.jd_processing_status === "processing")
        ? 2000
        : false;
    },
  });

  const { data: docData } = useQuery({
    queryKey: ["documents", projectId],
    queryFn: () => getDocuments(projectId),
  });

  const positions = posData?.items ?? [];
  const allDocs = docData?.items ?? [];
  const jdDocs = allDocs.filter(
    (d) => d.doc_type === "jd" || d.doc_type === "job_description" || d.doc_type === "job_request"
  );

  const delMutation = useMutation({
    mutationFn: (id: number) => deletePosition(id).then(() => {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["positions", projectId] }),
  });

  function openNew(docId?: number) {
    setPrefillDocId(docId);
    setNewOpen(true);
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold text-gray-800">
          {positions.length} position{positions.length !== 1 ? "s" : ""}
        </h2>
        <Button
          className="bg-teal-600 hover:bg-teal-700 text-white gap-1.5"
          size="sm"
          onClick={() => openNew()}
        >
          <Plus className="w-4 h-4" /> New Position
        </Button>
      </div>

      {positions.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <Briefcase className="w-10 h-10 mx-auto mb-3 opacity-40" />
          <p className="text-sm">No positions yet.</p>
          <Button
            className="mt-3 bg-teal-600 hover:bg-teal-700 text-white"
            size="sm"
            onClick={() => openNew()}
          >
            Create first position
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {positions.map((pos) => (
            <Link key={pos.id} href={`/positions/${pos.id}`}>
              <Card className="bg-white border border-gray-200 rounded-xl hover:shadow-md transition-shadow cursor-pointer">
                <CardContent className="p-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <PositionStatusDot status={pos.status} />
                      <span className="font-semibold text-gray-900 text-sm truncate">{pos.title}</span>
                    </div>
                    <button
                      className="p-1 rounded hover:bg-red-50 text-gray-400 hover:text-red-500 shrink-0"
                      onClick={(e) => { e.preventDefault(); delMutation.mutate(pos.id); }}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  {/* JD status indicator */}
                  {pos.jd_processing_status && pos.jd_processing_status !== "processed" && (
                    <div className="mt-2 flex items-center gap-1 text-xs text-teal-600">
                      <Loader2 className="w-3 h-3 animate-spin" />
                      Analyzing JD…
                    </div>
                  )}
                  {pos.jd_processing_status === "processed" && pos.jd_summary && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {(pos.jd_summary.required_skills as string[] ?? []).slice(0, 3).map((s, i) => (
                        <span key={i} className="text-xs bg-teal-50 text-teal-700 px-1.5 py-0.5 rounded-full">
                          {s}
                        </span>
                      ))}
                    </div>
                  )}
                  {!pos.jd_document_id && (
                    <div className="mt-2 text-xs text-amber-500 flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3" /> No JD linked
                    </div>
                  )}

                  <div className="mt-3 flex items-center gap-4 text-xs text-gray-500">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {pos.days_open}d open
                    </span>
                    <span className="flex items-center gap-1">
                      <UserRound className="w-3 h-3" />
                      {pos.candidates_count} candidate{pos.candidates_count !== 1 ? "s" : ""}
                    </span>
                    {pos.level && (
                      <Badge variant="secondary" className="text-xs h-5">
                        {pos.level}
                      </Badge>
                    )}
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}

      <NewPositionDialog
        projectId={projectId}
        jdDocs={jdDocs}
        open={newOpen}
        onClose={() => setNewOpen(false)}
        prefillDocId={prefillDocId}
      />
    </div>
  );
}

// ── Analysis Tab ──────────────────────────────────────────────────────────────

function AnalysisTab({ projectId }: { projectId: number }) {
  const qc = useQueryClient();

  const { data: docs } = useQuery({
    queryKey: ["documents", projectId],
    queryFn: () => getDocuments(projectId),
  });

  const { data: results, refetch: refetchResults } = useQuery({
    queryKey: ["analysis", projectId],
    queryFn: () => getAnalysisResults(projectId),
  });

  const documents = docs?.items ?? [];
  const analysisResults = results ?? [];

  function onRun() {
    refetchResults();
    qc.invalidateQueries({ queryKey: ["analysis", projectId] });
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {(["A", "B", "C", "D", "E"] as const).map((mode) => (
        <AnalysisModeCard
          key={mode}
          mode={mode}
          projectId={projectId}
          documents={documents}
          existingResults={analysisResults}
          onRun={onRun}
        />
      ))}
    </div>
  );
}


// ── Team Tab ──────────────────────────────────────────────────────────────────

const LEVELS = ["junior", "mid", "senior", "lead"];

function SkillsOverview({ overview }: { overview: Record<string, unknown> | undefined }) {
  if (!overview) return null;
  const matrix = (overview.skills_matrix as Array<{ skill: string; count: number }>) ?? [];
  const total = (overview.active_count as number) || 1;
  if (matrix.length === 0) return null;

  return (
    <Card className="bg-teal-50 border-teal-100">
      <CardContent className="p-4">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-sm font-semibold text-teal-800">Team Skills Coverage</span>
          <span className="text-xs text-teal-600">({overview.active_count as number} active members)</span>
        </div>
        <div className="grid grid-cols-2 gap-x-8 gap-y-1.5">
          {matrix.slice(0, 10).map(({ skill, count }) => (
            <div key={skill} className="flex items-center gap-2">
              <span className="text-xs text-gray-600 w-28 truncate shrink-0">{skill}</span>
              <div className="flex-1 bg-teal-100 rounded-full h-1.5">
                <div
                  className="bg-teal-500 h-1.5 rounded-full"
                  style={{ width: `${Math.min(100, (count / total) * 100)}%` }}
                />
              </div>
              <span className="text-xs text-teal-700 font-medium w-4">{count}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function MemberCard({
  m,
  onOffboard,
  onPreviewResume,
}: {
  m: TeamMember;
  onOffboard: (id: number) => void;
  onPreviewResume: (docId: number) => void;
}) {
  const router = useRouter();
  const initials = m.name.split(" ").map((w: string) => w[0]).join("").slice(0, 2).toUpperCase();
  const sinceDate = m.start_date
    ? new Date(m.start_date).toLocaleDateString("en-GB", { month: "short", year: "numeric" })
    : null;
  const lastReport = m.last_report_date
    ? new Date(m.last_report_date).toLocaleDateString("en-GB", { day: "numeric", month: "short" })
    : null;

  return (
    <Card
      className={`border cursor-pointer hover:shadow-md transition-shadow ${m.status === "offboarded" ? "border-gray-100 opacity-60" : "border-gray-200"}`}
      onClick={() => router.push(`/team/${m.id}`)}
    >
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-full font-semibold flex items-center justify-center text-sm shrink-0
              ${m.status === "offboarded" ? "bg-gray-100 text-gray-400" : "bg-teal-100 text-teal-700"}`}>
              {initials}
            </div>
            <div>
              <div className="font-semibold text-gray-900 text-sm">{m.name}</div>
              <div className="text-xs text-gray-500">{m.role}</div>
            </div>
          </div>
          <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
            {m.level && (
              <Badge className="text-xs bg-purple-50 text-purple-600 border-0 px-1.5">{m.level}</Badge>
            )}
            {m.status === "offboarded" && (
              <Badge className="text-xs bg-gray-100 text-gray-400 border-0 px-1.5">off</Badge>
            )}
            {m.status === "active" && (
              <Button
                variant="ghost"
                size="icon"
                className="w-6 h-6 text-gray-300 hover:text-red-400"
                title="Offboard member"
                onClick={() => onOffboard(m.id)}
              >
                <Trash2 className="w-3 h-3" />
              </Button>
            )}
          </div>
        </div>

        {/* Skills */}
        {m.skills && m.skills.length > 0 && (
          <div className="mt-2.5 flex flex-wrap gap-1">
            {m.skills.slice(0, 6).map((s: string) => (
              <span key={s} className="px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">{s}</span>
            ))}
            {m.skills.length > 6 && (
              <span className="px-1.5 py-0.5 text-gray-400 text-xs">+{m.skills.length - 6}</span>
            )}
          </div>
        )}

        {/* Footer meta */}
        <div className="mt-2.5 flex items-center gap-3 text-xs text-gray-400" onClick={(e) => e.stopPropagation()}>
          {sinceDate && <span>Since {sinceDate}</span>}
          {m.resume_document_id ? (
            <button
              className="flex items-center gap-0.5 text-teal-600 hover:text-teal-700"
              onClick={() => onPreviewResume(m.resume_document_id!)}
              title="Preview resume"
            >
              <FileText className="w-3 h-3" /> Resume
            </button>
          ) : (
            <span className="text-amber-500">No resume</span>
          )}
          {m.reports_count > 0 && (
            <span className="flex items-center gap-0.5">
              <UserRound className="w-3 h-3" />
              {m.reports_count} report{m.reports_count !== 1 ? "s" : ""}
              {lastReport && <span className="ml-1 text-gray-300">(last {lastReport})</span>}
            </span>
          )}
          <span className="ml-auto text-gray-300 hover:text-teal-500">→</span>
        </div>
      </CardContent>
    </Card>
  );
}

function TeamTab({ projectId }: { projectId: number }) {
  const queryClient = useQueryClient();
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [addForm, setAddForm] = useState({ name: "", role: "", level: "", start_date: "", notes: "" });
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const resumeRef = useRef<HTMLInputElement>(null);
  const [previewDocId, setPreviewDocId] = useState<number | null>(null);

  const { data: teamData, isLoading } = useQuery({
    queryKey: ["team", projectId],
    queryFn: () => getTeam(projectId),
  });

  const addMutation = useMutation({
    mutationFn: (fd: FormData) => addTeamMember(projectId, fd),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["team", projectId] });
      setShowAddDialog(false);
      setAddForm({ name: "", role: "", level: "", start_date: "", notes: "" });
      setResumeFile(null);
    },
  });

  const offboardMutation = useMutation({
    mutationFn: deleteTeamMember,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["team", projectId] }),
  });

  const handleAdd = () => {
    const fd = new FormData();
    Object.entries(addForm).forEach(([k, v]) => fd.append(k, v));
    if (resumeFile) fd.append("file", resumeFile);
    addMutation.mutate(fd);
  };

  const members: TeamMember[] = teamData?.items ?? [];
  const overview = teamData?.overview as Record<string, unknown> | undefined;

  // Group by role
  const grouped: Record<string, TeamMember[]> = {};
  for (const m of members) {
    const key = m.role || "Other";
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(m);
  }

  return (
    <div className="space-y-4">
      {previewDocId !== null && (
        <DocumentPreviewSheet documentId={previewDocId} onClose={() => setPreviewDocId(null)} />
      )}
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">
            Current Team {members.length > 0 && <span className="text-gray-400 font-normal text-base">({members.length})</span>}
          </h3>
          <p className="text-sm text-gray-500">
            Resumes and reports are used as foundation for all AI analysis
          </p>
        </div>
        <Button onClick={() => setShowAddDialog(true)} size="sm" className="bg-teal-600 hover:bg-teal-700">
          <Plus className="w-4 h-4 mr-1" /> Add Member
        </Button>
      </div>

      {isLoading && (
        <div className="flex items-center gap-2 text-gray-400 py-8 justify-center">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading team...
        </div>
      )}

      {/* Skills Overview */}
      {!isLoading && members.length > 0 && <SkillsOverview overview={overview} />}

      {/* Empty state */}
      {!isLoading && members.length === 0 && (
        <Card className="border-dashed">
          <CardContent className="py-12 text-center">
            <Users className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 font-medium">No team members yet</p>
            <p className="text-sm text-gray-400 mt-1 max-w-xs mx-auto">
              Add your current team with their resumes to power AI historical insights
            </p>
            <Button onClick={() => setShowAddDialog(true)} variant="outline" size="sm" className="mt-4">
              Add First Team Member
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Members grouped by role */}
      {Object.entries(grouped).map(([role, roleMembers]) => (
        <div key={role}>
          <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2 flex items-center gap-2">
            <span>{role}</span>
            <div className="flex-1 border-t border-gray-100" />
            <span>{roleMembers.length}</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {roleMembers.map((m) => (
              <MemberCard key={m.id} m={m} onOffboard={(id) => offboardMutation.mutate(id)} onPreviewResume={setPreviewDocId} />
            ))}
          </div>
        </div>
      ))}

      {/* Add Dialog */}
      <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Add Team Member</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 mt-2">
            <div>
              <label className="text-xs font-medium text-gray-600 mb-1 block">Full Name *</label>
              <Input placeholder="e.g. Alex Johnson" value={addForm.name}
                onChange={(e) => setAddForm((p) => ({ ...p, name: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 mb-1 block">Role *</label>
              <Input placeholder="e.g. Senior Backend Developer" value={addForm.role}
                onChange={(e) => setAddForm((p) => ({ ...p, role: e.target.value }))} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-gray-600 mb-1 block">Level</label>
                <Select value={addForm.level} onValueChange={(v) => setAddForm((p) => ({ ...p, level: v ?? "" }))}>
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
                <Input type="date" value={addForm.start_date}
                  onChange={(e) => setAddForm((p) => ({ ...p, start_date: e.target.value }))} />
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 mb-1 block">
                Resume — optional, skills auto-extracted by AI
              </label>
              <div
                className="border-2 border-dashed border-gray-200 rounded-lg p-3 text-center cursor-pointer hover:border-teal-400 transition-colors"
                onClick={() => resumeRef.current?.click()}
              >
                {resumeFile
                  ? <p className="text-sm text-teal-600 font-medium">{resumeFile.name}</p>
                  : <p className="text-sm text-gray-400">Click to select PDF / DOC / DOCX</p>}
              </div>
              <input ref={resumeRef} type="file" accept=".pdf,.doc,.docx,.txt" className="hidden"
                onChange={(e) => setResumeFile(e.target.files?.[0] ?? null)} />
              <p className="text-xs text-gray-400 mt-1">
                AI will extract skills and experience to build team context
              </p>
            </div>
            <div className="flex gap-2 justify-end pt-1">
              <Button variant="outline" onClick={() => setShowAddDialog(false)}>Cancel</Button>
              <Button
                className="bg-teal-600 hover:bg-teal-700"
                disabled={!addForm.name.trim() || !addForm.role.trim() || addMutation.isPending}
                onClick={handleAdd}
              >
                {addMutation.isPending && <Loader2 className="w-4 h-4 animate-spin mr-1" />}
                Add Member
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ProjectDetail() {
  const params = useParams();
  const projectId = Number(params.id);
  const router = useRouter();

  const { data: project, isLoading } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400">
        <Loader2 className="w-6 h-6 animate-spin" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="text-center py-16 text-gray-400">
        <p>Project not found.</p>
        <Link href="/" className="text-teal-600 hover:underline text-sm mt-2 inline-block">
          Back to Dashboard
        </Link>
      </div>
    );
  }

  return (
    <>
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => router.push("/")}
          className="p-1.5 rounded-lg hover:bg-gray-200 text-gray-500"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div>
          <h1 className="text-[22px] font-bold text-gray-900">{project.name}</h1>
          <p className="text-sm text-gray-500">{project.client_name}</p>
        </div>
        <div className="ml-auto">
          <Badge
            className={
              project.status === "active"
                ? "bg-teal-50 text-teal-700 border-teal-200"
                : "bg-gray-100 text-gray-600"
            }
          >
            {project.status}
          </Badge>
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="team">
        <TabsList className="bg-gray-100 mb-6">
          <TabsTrigger value="team">Team</TabsTrigger>
          <TabsTrigger value="positions">Positions</TabsTrigger>
          <TabsTrigger value="documents">Documents</TabsTrigger>
          <TabsTrigger value="analysis">AI Analysis</TabsTrigger>
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
        </TabsList>

        <TabsContent value="team">
          <TeamTab projectId={projectId} />
        </TabsContent>

        <TabsContent value="positions">
          <PositionsTab projectId={projectId} />
        </TabsContent>

        <TabsContent value="documents">
          <DocumentsTab projectId={projectId} />
        </TabsContent>

        <TabsContent value="analysis">
          <AnalysisTab projectId={projectId} />
        </TabsContent>

        <TabsContent value="timeline">
          <div className="text-center py-16 text-gray-400 text-sm">
            Timeline coming soon.
          </div>
        </TabsContent>
      </Tabs>
    </>
  );
}
