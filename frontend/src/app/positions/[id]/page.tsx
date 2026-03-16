"use client";

import { useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Upload,
  Loader2,
  Clock,
  UserRound,
  Trash2,
  RotateCcw,
  ChevronDown,
  AlertTriangle,
  FileText,
  RefreshCw,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  getPosition,
  getDocuments,
  getCandidates,
  getCandidate,
  addCandidate,
  updateCandidate,
  deleteCandidate,
  scoreCandidate,
  scoreAllCandidates,
  updatePosition,
  replacePositionJd,
  getAnalysisResults,
  downloadDocument,
  runJDRealityCheck,
  type Position,
  type Candidate,
  type Document,
} from "@/lib/api";

// ── Helpers ───────────────────────────────────────────────────────────────────

const CANDIDATE_STATUSES = [
  { value: "new", label: "New", color: "bg-gray-100 text-gray-600" },
  { value: "screening", label: "Screening", color: "bg-blue-100 text-blue-700" },
  { value: "technical_interview", label: "Technical", color: "bg-purple-100 text-purple-700" },
  { value: "client_interview", label: "Client", color: "bg-orange-100 text-orange-700" },
  { value: "offer", label: "Offer", color: "bg-yellow-100 text-yellow-700" },
  { value: "hired", label: "Hired", color: "bg-emerald-100 text-emerald-700" },
  { value: "rejected", label: "Rejected", color: "bg-red-100 text-red-600" },
];

function statusColor(status: string) {
  return CANDIDATE_STATUSES.find((s) => s.value === status)?.color ?? "bg-gray-100 text-gray-600";
}

function statusLabel(status: string) {
  return CANDIDATE_STATUSES.find((s) => s.value === status)?.label ?? status;
}

function scoreColor(score?: number) {
  if (!score && score !== 0) return "text-gray-400";
  if (score >= 70) return "text-emerald-600";
  if (score >= 50) return "text-amber-600";
  return "text-red-600";
}

function scoreBg(score?: number) {
  if (!score && score !== 0) return "bg-gray-50";
  if (score >= 70) return "bg-emerald-50";
  if (score >= 50) return "bg-amber-50";
  return "bg-red-50";
}

function verdictBadge(verdict?: string) {
  const map: Record<string, string> = {
    strong_fit: "bg-emerald-100 text-emerald-700",
    moderate_fit: "bg-blue-100 text-blue-700",
    risky: "bg-amber-100 text-amber-700",
    not_recommended: "bg-red-100 text-red-600",
  };
  if (!verdict) return null;
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${map[verdict] ?? "bg-gray-100 text-gray-600"}`}>
      {verdict.replace(/_/g, " ")}
    </span>
  );
}

// ── Replace JD Dialog ─────────────────────────────────────────────────────────

function ReplaceJdDialog({
  positionId,
  jdDocs,
  open,
  onClose,
}: {
  positionId: number;
  jdDocs: Document[];
  open: boolean;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<"upload" | "existing">("upload");
  const [file, setFile] = useState<File | null>(null);
  const [selectedDocId, setSelectedDocId] = useState<number | undefined>();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit() {
    setError("");
    setLoading(true);
    try {
      await replacePositionJd(positionId, {
        file: mode === "upload" && file ? file : undefined,
        jd_document_id: mode === "existing" ? selectedDocId : undefined,
      });
      qc.invalidateQueries({ queryKey: ["position", positionId] });
      setFile(null); setSelectedDocId(undefined);
      onClose();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to update JD");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Upload Job Description</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <div className="flex gap-2">
            <Button
              variant={mode === "upload" ? "default" : "outline"}
              size="sm"
              className={mode === "upload" ? "bg-teal-600 hover:bg-teal-700 text-white" : ""}
              onClick={() => setMode("upload")}
            >
              Upload New
            </Button>
            {jdDocs.length > 0 && (
              <Button
                variant={mode === "existing" ? "default" : "outline"}
                size="sm"
                className={mode === "existing" ? "bg-teal-600 hover:bg-teal-700 text-white" : ""}
                onClick={() => setMode("existing")}
              >
                Choose Uploaded ({jdDocs.length})
              </Button>
            )}
          </div>

          {mode === "upload" ? (
            <div
              className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center cursor-pointer hover:border-teal-400 transition-colors"
              onClick={() => fileRef.current?.click()}
            >
              <Upload className="w-6 h-6 text-gray-400 mx-auto mb-2" />
              {file ? (
                <p className="text-sm text-gray-700">{file.name}</p>
              ) : (
                <p className="text-sm text-gray-500">Click to upload JD (PDF, DOC, DOCX, TXT)</p>
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
            <Select
              value={selectedDocId ? String(selectedDocId) : "none"}
              onValueChange={(v) => setSelectedDocId(v === "none" ? undefined : Number(v))}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select uploaded JD…" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Choose…</SelectItem>
                {jdDocs.map((d) => (
                  <SelectItem key={d.id} value={String(d.id)}>
                    {d.original_filename}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          {error && <p className="text-sm text-red-500">{error}</p>}

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button
              className="bg-teal-600 hover:bg-teal-700 text-white"
              disabled={loading || (mode === "upload" && !file) || (mode === "existing" && !selectedDocId)}
              onClick={handleSubmit}
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Save JD"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ── JD Section ────────────────────────────────────────────────────────────────

function JdSection({
  position,
  jdDocs,
  onOpenJdDialog,
}: {
  position: Position;
  jdDocs: Document[];
  onOpenJdDialog: () => void;
}) {
  const jdStatus = position.jd_processing_status;
  const jdSummary = position.jd_summary as Record<string, unknown> | null | undefined;
  const isProcessing = jdStatus === "queued" || jdStatus === "processing";
  const isProcessed = jdStatus === "processed";

  if (!position.jd_document_id) {
    return (
      <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-xl flex items-center justify-between">
        <div className="flex items-center gap-2 text-amber-700">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span className="text-sm font-medium">No Job Description attached</span>
          <span className="text-xs text-amber-600">— upload a JD to enable AI scoring</span>
        </div>
        <Button
          size="sm"
          className="bg-amber-600 hover:bg-amber-700 text-white gap-1.5"
          onClick={onOpenJdDialog}
        >
          <Upload className="w-3.5 h-3.5" /> Upload JD
        </Button>
      </div>
    );
  }

  if (isProcessing) {
    return (
      <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-xl flex items-center justify-between">
        <div className="flex items-center gap-2 text-blue-700">
          <Loader2 className="w-4 h-4 animate-spin shrink-0" />
          <span className="text-sm font-medium">Analyzing Job Description…</span>
          <span className="text-xs text-blue-500">This usually takes a few seconds</span>
        </div>
        <Button size="sm" variant="ghost" className="text-blue-600 gap-1" onClick={onOpenJdDialog}>
          <RefreshCw className="w-3.5 h-3.5" /> Replace
        </Button>
      </div>
    );
  }

  if (isProcessed && jdSummary) {
    const skills = [
      ...((jdSummary.required_skills as string[]) ?? []),
      ...((jdSummary.preferred_skills as string[]) ?? []),
    ];
    const requirements = (jdSummary.requirements as string[]) ?? [];
    const title = jdSummary.title as string | undefined;
    const location = jdSummary.location as string | undefined;
    const employmentType = jdSummary.employment_type as string | undefined;
    const seniorityLevel = jdSummary.seniority_level as string | undefined;
    const salaryRange = jdSummary.salary_range as string | undefined;

    return (
      <Card className="mb-6 bg-white border border-gray-200">
        <CardHeader className="pb-2 flex flex-row items-start justify-between">
          <div>
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-teal-600" />
              <CardTitle className="text-sm font-semibold text-gray-700">Job Description</CardTitle>
              {title && <span className="text-sm text-gray-500">— {title}</span>}
            </div>
            <div className="flex gap-3 mt-1 text-xs text-gray-400 flex-wrap">
              {location && <span>{location}</span>}
              {employmentType && <span>{employmentType}</span>}
              {seniorityLevel && <span className="capitalize">{seniorityLevel}</span>}
              {salaryRange && <span>{salaryRange}</span>}
            </div>
          </div>
          <Button size="sm" variant="ghost" className="text-gray-400 hover:text-gray-600 gap-1 text-xs" onClick={onOpenJdDialog}>
            <RefreshCw className="w-3 h-3" /> Replace
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          {skills.length > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-500 mb-1.5">Skills</p>
              <div className="flex flex-wrap gap-1.5">
                {skills.slice(0, 12).map((s, i) => (
                  <span
                    key={i}
                    className={`text-xs px-2 py-0.5 rounded-full ${
                      i < ((jdSummary.required_skills as string[]) ?? []).length
                        ? "bg-teal-100 text-teal-700"
                        : "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {s}
                  </span>
                ))}
                {skills.length > 12 && (
                  <span className="text-xs text-gray-400">+{skills.length - 12} more</span>
                )}
              </div>
            </div>
          )}
          {requirements.length > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-500 mb-1">Requirements</p>
              <ul className="space-y-0.5">
                {requirements.slice(0, 4).map((r, i) => (
                  <li key={i} className="text-xs text-gray-600 flex gap-1.5">
                    <span className="text-teal-500 mt-0.5 shrink-0">•</span>
                    {r}
                  </li>
                ))}
                {requirements.length > 4 && (
                  <li className="text-xs text-gray-400">+{requirements.length - 4} more</li>
                )}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>
    );
  }

  // JD linked but not processed yet (e.g. status=error or no summary)
  return (
    <div className="mb-6 p-4 bg-gray-50 border border-gray-200 rounded-xl flex items-center justify-between">
      <div className="flex items-center gap-2 text-gray-500">
        <FileText className="w-4 h-4 shrink-0" />
        <span className="text-sm">JD attached</span>
        {jdStatus === "error" && <span className="text-xs text-red-500">(processing error)</span>}
      </div>
      <Button size="sm" variant="ghost" className="text-gray-500 gap-1 text-xs" onClick={onOpenJdDialog}>
        <RefreshCw className="w-3 h-3" /> Replace
      </Button>
    </div>
  );
}

// ── Add Candidate Dialog ──────────────────────────────────────────────────────

function AddCandidateDialog({
  positionId,
  resumeDocs,
  open,
  onClose,
}: {
  positionId: number;
  resumeDocs: Document[];
  open: boolean;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<"existing" | "upload">("existing");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [selectedDocId, setSelectedDocId] = useState<number | undefined>();
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit() {
    setError("");
    setLoading(true);
    try {
      await addCandidate(
        positionId,
        {
          name: name || undefined,
          email: email || undefined,
          resume_document_id: mode === "existing" ? selectedDocId : undefined,
        },
        mode === "upload" && file ? file : undefined
      );
      qc.invalidateQueries({ queryKey: ["candidates", positionId] });
      setName(""); setEmail(""); setSelectedDocId(undefined); setFile(null);
      onClose();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to add candidate");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add Candidate</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">
          {/* Mode toggle */}
          <div className="flex gap-2">
            <Button
              variant={mode === "existing" ? "default" : "outline"}
              size="sm"
              className={mode === "existing" ? "bg-teal-600 hover:bg-teal-700 text-white" : ""}
              onClick={() => setMode("existing")}
            >
              Select Resume
            </Button>
            <Button
              variant={mode === "upload" ? "default" : "outline"}
              size="sm"
              className={mode === "upload" ? "bg-teal-600 hover:bg-teal-700 text-white" : ""}
              onClick={() => setMode("upload")}
            >
              Upload Resume
            </Button>
          </div>

          {mode === "existing" ? (
            <Select
              value={selectedDocId ? String(selectedDocId) : "none"}
              onValueChange={(v) => setSelectedDocId(v === "none" ? undefined : Number(v))}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select uploaded resume…" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Choose…</SelectItem>
                {resumeDocs.map((d) => (
                  <SelectItem key={d.id} value={String(d.id)}>
                    {d.original_filename}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : (
            <div
              className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center cursor-pointer hover:border-teal-400 transition-colors"
              onClick={() => fileRef.current?.click()}
            >
              <Upload className="w-6 h-6 text-gray-400 mx-auto mb-2" />
              {file ? (
                <p className="text-sm text-gray-700">{file.name}</p>
              ) : (
                <p className="text-sm text-gray-500">Click to upload resume (PDF, DOC, DOCX)</p>
              )}
              <input
                ref={fileRef}
                type="file"
                accept=".pdf,.doc,.docx,.txt"
                className="hidden"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </div>
          )}

          <div>
            <label className="text-sm font-medium text-gray-700">Name (auto-filled if not set)</label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Jane Smith" className="mt-1" />
          </div>
          <div>
            <label className="text-sm font-medium text-gray-700">Email (optional)</label>
            <Input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="jane@example.com" className="mt-1" />
          </div>

          {error && <p className="text-sm text-red-500">{error}</p>}

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button
              className="bg-teal-600 hover:bg-teal-700 text-white"
              disabled={loading || (mode === "existing" && !selectedDocId) || (mode === "upload" && !file)}
              onClick={handleSubmit}
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Add Candidate"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ── CV Panel ──────────────────────────────────────────────────────────────────

function CvPanel({ candidateId, onClose }: { candidateId: number; onClose: () => void }) {
  const { data: candidate, isLoading } = useQuery({
    queryKey: ["candidate-detail", candidateId],
    queryFn: () => getCandidate(candidateId),
  });

  const extracted = candidate?.resume_extracted as Record<string, unknown> | undefined;

  function renderList(items: unknown) {
    if (!Array.isArray(items) || items.length === 0) return null;
    return (
      <ul className="space-y-1 mt-1">
        {items.slice(0, 8).map((item, i) => (
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

  const downloadUrl = candidate?.resume_document_id
    ? downloadDocument(candidate.resume_document_id)
    : null;

  return (
    <>
      <div className="fixed inset-0 bg-black/20 z-40" onClick={onClose} />
      <div className="fixed right-0 top-0 h-full w-[40%] bg-white z-50 shadow-xl overflow-y-auto flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 shrink-0">
          <div>
            <h2 className="text-base font-semibold text-gray-900">{candidate?.name ?? "Loading…"}</h2>
            {candidate?.location && <p className="text-xs text-gray-400">{candidate.location}</p>}
          </div>
          <div className="flex items-center gap-2">
            {downloadUrl && (
              <a
                href={downloadUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs px-3 py-1.5 rounded-md bg-teal-600 text-white hover:bg-teal-700 flex items-center gap-1"
              >
                <FileText className="w-3.5 h-3.5" /> Download CV
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

          {extracted && (
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

              {(extracted.skills || extracted.required_skills) && (
                <div>
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Skills</p>
                  <div className="flex flex-wrap gap-1.5 mt-1">
                    {(Array.isArray(extracted.skills) ? extracted.skills : Array.isArray(extracted.required_skills) ? extracted.required_skills : []).slice(0, 20).map((s, i) => (
                      <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-teal-50 text-teal-700 border border-teal-100">
                        {String(s)}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {extracted.education && (
                <div>
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Education</p>
                  {renderList(extracted.education)}
                </div>
              )}

              {!extracted.summary && !extracted.work_history && !extracted.skills && (
                <div className="text-sm text-gray-400 py-8 text-center">
                  Resume content is processing or unavailable.
                </div>
              )}
            </>
          )}

          {!isLoading && !extracted && (
            <div className="text-sm text-gray-400 py-8 text-center">
              No extracted resume content available.
            </div>
          )}
        </div>
      </div>
    </>
  );
}

// ── Candidate Row ─────────────────────────────────────────────────────────────

function CandidateRow({
  candidate,
  rank,
  positionId,
}: {
  candidate: Candidate;
  rank: number;
  positionId: number;
}) {
  const qc = useQueryClient();
  const [scoring, setScoring] = useState(false);
  const [scoreErr, setScoreErr] = useState("");
  const [expanded, setExpanded] = useState(false);
  const [cvOpen, setCvOpen] = useState(false);

  const statusMutation = useMutation({
    mutationFn: (status: string) => updateCandidate(candidate.id, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["candidates", positionId] }),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteCandidate(candidate.id).then(() => {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["candidates", positionId] }),
  });

  async function handleScore() {
    setScoreErr("");
    setScoring(true);
    try {
      await scoreCandidate(candidate.id);
      qc.invalidateQueries({ queryKey: ["candidates", positionId] });
    } catch (e: unknown) {
      setScoreErr(e instanceof Error ? e.message : "Scoring failed");
    } finally {
      setScoring(false);
    }
  }

  const noResume = !candidate.resume_document_id;

  const margin = candidate.margin as Record<string, unknown> | undefined;
  const marginPct = margin?.is_calculated ? Number(margin.margin_percentage) : null;
  const marginColor = marginPct == null ? "text-gray-300" : marginPct >= 40 ? "text-emerald-600" : marginPct >= 25 ? "text-amber-600" : "text-red-600";

  return (
    <>
      {cvOpen && <CvPanel candidateId={candidate.id} onClose={() => setCvOpen(false)} />}
      <tr className="hover:bg-gray-50">
        {/* # */}
        <td className="py-3 px-3 text-gray-400 text-sm font-medium">#{rank}</td>
        {/* Name */}
        <td className="py-3 px-3">
          <Link
            href={`/candidates/${candidate.id}`}
            className="font-medium text-gray-900 text-sm hover:text-teal-600"
            onClick={(e) => e.stopPropagation()}
          >
            {candidate.name}
          </Link>
          {candidate.email && (
            <div className="text-xs text-gray-400">{candidate.email}</div>
          )}
        </td>
        {/* Score */}
        <td className="py-3 px-3">
          {candidate.ai_score != null ? (
            <div className={`inline-flex items-center justify-center w-10 h-10 rounded-full font-bold text-sm ${scoreBg(candidate.ai_score)} ${scoreColor(candidate.ai_score)}`}>
              {Math.round(candidate.ai_score)}
            </div>
          ) : (
            <span className="text-sm text-gray-300 font-medium">—</span>
          )}
        </td>
        {/* Verdict */}
        <td className="py-3 px-3">
          {candidate.ai_verdict ? verdictBadge(candidate.ai_verdict) : (
            <span className="text-xs text-gray-300">pending</span>
          )}
        </td>
        {/* Skills Match */}
        <td className="py-3 px-3">
          {candidate.skill_match_score != null ? (
            <div className="flex items-center gap-1.5">
              <div className="w-14 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${candidate.skill_match_score >= 70 ? "bg-emerald-400" : candidate.skill_match_score >= 50 ? "bg-amber-400" : "bg-red-400"}`}
                  style={{ width: `${Math.min(candidate.skill_match_score, 100)}%` }}
                />
              </div>
              <span className="text-xs text-gray-500">{Math.round(candidate.skill_match_score)}%</span>
            </div>
          ) : (
            <span className="text-xs text-gray-300">—</span>
          )}
        </td>
        {/* Experience */}
        <td className="py-3 px-3 text-sm text-gray-600">
          {candidate.years_of_experience != null
            ? `${candidate.years_of_experience}y`
            : <span className="text-gray-300">—</span>}
        </td>
        {/* Margin */}
        <td className="py-3 px-3">
          {marginPct != null ? (
            <span className={`text-xs font-medium ${marginColor}`}>{marginPct}%</span>
          ) : (
            <span className="text-xs text-gray-300">—</span>
          )}
        </td>
        {/* Status */}
        <td className="py-3 px-3" onClick={(e) => e.stopPropagation()}>
          <Select
            value={candidate.status}
            onValueChange={(v) => v && statusMutation.mutate(v)}
          >
            <SelectTrigger className="h-7 text-xs w-32 border-0 shadow-none p-0 focus:ring-0">
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusColor(candidate.status)}`}>
                {statusLabel(candidate.status)}
              </span>
            </SelectTrigger>
            <SelectContent>
              {CANDIDATE_STATUSES.map((s) => (
                <SelectItem key={s.value} value={s.value}>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${s.color}`}>{s.label}</span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </td>
        {/* Analyzed */}
        <td className="py-3 px-3 text-xs text-gray-400">
          {candidate.scored_at
            ? new Date(candidate.scored_at).toLocaleDateString()
            : <span className="text-gray-300">Not analyzed</span>}
        </td>
        {/* Actions */}
        <td className="py-3 px-3" onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center gap-1">
            {candidate.resume_document_id && (
              <button
                className="p-1 rounded hover:bg-teal-50 text-gray-400 hover:text-teal-600"
                onClick={() => setCvOpen(true)}
                title="Preview CV"
              >
                <FileText className="w-3.5 h-3.5" />
              </button>
            )}
            <Link
              href={`/candidates/${candidate.id}`}
              className="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-teal-600"
              title="View profile"
            >
              <ChevronDown className="w-3.5 h-3.5 -rotate-90" />
            </Link>
            {!noResume && (
              <button
                className="p-1 rounded hover:bg-teal-50 text-gray-400 hover:text-teal-600 disabled:opacity-50"
                onClick={() => handleScore()}
                disabled={scoring}
                title={scoreErr || "Re-analyze with latest JD data"}
              >
                {scoring ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RotateCcw className="w-3.5 h-3.5" />}
              </button>
            )}
            <button
              className="p-1 rounded hover:bg-red-50 text-gray-400 hover:text-red-500"
              onClick={() => deleteMutation.mutate()}
              title="Remove candidate"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
          {scoreErr && (
            <p className="text-xs text-red-500 mt-0.5 max-w-[120px] truncate" title={scoreErr}>{scoreErr}</p>
          )}
        </td>
        {/* Expand */}
        <td className="py-3 px-2 text-gray-300 cursor-pointer" onClick={() => setExpanded(e => !e)}>
          <ChevronDown className={`w-4 h-4 transition-transform ${expanded ? "rotate-180" : ""}`} />
        </td>
      </tr>
      {expanded && (
        <tr className="bg-gray-50">
          <td colSpan={11} className="px-4 pb-3 pt-1">
            {candidate.ai_score != null ? (
              <div className="text-xs text-gray-500 space-y-1">
                <p className="font-medium text-gray-700">AI Score Breakdown</p>
                <p>Overall: <strong className={scoreColor(candidate.ai_score)}>{candidate.ai_score}/100</strong></p>
                {candidate.ai_verdict && <p>Verdict: {candidate.ai_verdict.replace(/_/g, " ")}</p>}
                {candidate.skill_match_score != null && <p>Skills match: {candidate.skill_match_score}%</p>}
                {candidate.years_of_experience != null && <p>Experience: {candidate.years_of_experience}y</p>}
                {candidate.notes && <p className="italic text-gray-400">Note: {candidate.notes}</p>}
                <p className="text-gray-400 italic">View profile for full reasoning</p>
              </div>
            ) : noResume ? (
              <p className="text-xs text-gray-400">No resume uploaded — add a resume to enable AI scoring.</p>
            ) : (
              <p className="text-xs text-gray-400">Not analyzed yet. Use the re-score button or &ldquo;Analyze Candidates&rdquo; above.</p>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function PositionDetail() {
  const params = useParams();
  const positionId = Number(params.id);
  const router = useRouter();
  const qc = useQueryClient();
  const [addOpen, setAddOpen] = useState(false);
  const [jdDialogOpen, setJdDialogOpen] = useState(false);
  const [scoringAll, setScoringAll] = useState(false);
  const [scoreError, setScoreError] = useState("");
  const [runningRealityCheck, setRunningRealityCheck] = useState(false);
  const [realityCheckError, setRealityCheckError] = useState("");
  const [clientRateEdit, setClientRateEdit] = useState(false);
  const [clientRateDraft, setClientRateDraft] = useState("");
  const [clientRatePeriodDraft, setClientRatePeriodDraft] = useState("monthly");

  const { data: position, isLoading: posLoading } = useQuery({
    queryKey: ["position", positionId],
    queryFn: () => getPosition(positionId),
    refetchInterval: (query) => {
      const pos = query.state.data;
      if (!pos) return false;
      const s = pos.jd_processing_status;
      return s === "queued" || s === "processing" ? 2_000 : false;
    },
  });

  const { data: candidates } = useQuery({
    queryKey: ["candidates", positionId],
    queryFn: () => getCandidates(positionId),
    refetchInterval: 5_000,
  });

  const { data: docData } = useQuery({
    queryKey: ["documents", position?.project_id],
    queryFn: () => getDocuments(position!.project_id),
    enabled: !!position?.project_id,
  });

  const { data: analysisResults } = useQuery({
    queryKey: ["analysis", position?.project_id],
    queryFn: () => getAnalysisResults(position!.project_id),
    enabled: !!position?.project_id,
  });

  const closeMutation = useMutation({
    mutationFn: () => updatePosition(positionId, { status: "filled" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["position", positionId] }),
  });

  const clientRateMutation = useMutation({
    mutationFn: (data: { client_rate?: number; client_rate_period?: string }) =>
      updatePosition(positionId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["position", positionId] });
      setClientRateEdit(false);
    },
  });

  function saveClientRate() {
    const rate = clientRateDraft ? parseFloat(clientRateDraft) : undefined;
    clientRateMutation.mutate({ client_rate: rate, client_rate_period: clientRatePeriodDraft });
  }

  async function handleScoreAll() {
    setScoreError("");
    setScoringAll(true);
    try {
      await scoreAllCandidates(positionId);
      qc.invalidateQueries({ queryKey: ["candidates", positionId] });
    } catch (e: unknown) {
      setScoreError(e instanceof Error ? e.message : "Scoring failed");
    } finally {
      setScoringAll(false);
    }
  }

  async function handleRealityCheck() {
    if (!position?.jd_document_id) return;
    setRealityCheckError("");
    setRunningRealityCheck(true);
    try {
      await runJDRealityCheck(position.jd_document_id);
      qc.invalidateQueries({ queryKey: ["analysis", position.project_id] });
    } catch (e: unknown) {
      setRealityCheckError(e instanceof Error ? e.message : "Reality check failed");
    } finally {
      setRunningRealityCheck(false);
    }
  }

  if (posLoading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400">
        <Loader2 className="w-6 h-6 animate-spin" />
      </div>
    );
  }

  if (!position) {
    return (
      <div className="text-center py-16 text-gray-400">
        <p>Position not found.</p>
      </div>
    );
  }

  const allCandidates = candidates?.items ?? [];
  const resumeDocs = (docData?.items ?? []).filter(
    (d) => d.doc_type === "resume" && d.status === "processed"
  );
  const jdDocs = (docData?.items ?? []).filter((d) => d.doc_type === "jd");

  // AI insights for this position's JD
  const talentBrief = (analysisResults ?? []).find(
    (r) => r.analysis_mode === "A" && position.jd_document_id && r.input_document_ids.includes(position.jd_document_id)
  );
  const levelAdvisor = (analysisResults ?? []).find(
    (r) => r.analysis_mode === "C" && position.jd_document_id && r.input_document_ids.includes(position.jd_document_id)
  );
  const realityCheck = (analysisResults ?? []).find(
    (r) => r.analysis_mode === "E" && position.jd_document_id && r.input_document_ids.includes(position.jd_document_id)
  );

  const unscoredCount = allCandidates.filter((c) => c.ai_score == null && c.resume_document_id).length;

  const positionStatusColors: Record<string, string> = {
    open: "bg-emerald-50 text-emerald-700 border-emerald-200",
    paused: "bg-amber-50 text-amber-700 border-amber-200",
    filled: "bg-blue-50 text-blue-700 border-blue-200",
    closed: "bg-gray-100 text-gray-600",
  };

  return (
    <>
      {/* Header */}
      <div className="flex items-start gap-3 mb-6">
        <button
          onClick={() => router.push(`/projects/${position.project_id}`)}
          className="p-1.5 rounded-lg hover:bg-gray-200 text-gray-500 mt-0.5"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-[22px] font-bold text-gray-900 truncate">{position.title}</h1>
            <Badge className={`border ${positionStatusColors[position.status] ?? "bg-gray-100 text-gray-600"}`}>
              {position.status}
            </Badge>
            {position.level && (
              <Badge variant="secondary" className="text-xs">{position.level}</Badge>
            )}
          </div>
          <div className="flex items-center gap-4 mt-1 text-sm text-gray-500 flex-wrap">
            <span className="flex items-center gap-1">
              <Clock className="w-3.5 h-3.5" />
              {position.days_open} day{position.days_open !== 1 ? "s" : ""} open
            </span>
            <span className="flex items-center gap-1">
              <UserRound className="w-3.5 h-3.5" />
              {allCandidates.length} candidate{allCandidates.length !== 1 ? "s" : ""}
            </span>
            {/* Client Rate inline editor */}
            {clientRateEdit ? (
              <span className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                <Input
                  value={clientRateDraft}
                  onChange={(e) => setClientRateDraft(e.target.value)}
                  placeholder="Rate"
                  className="h-6 text-xs w-20 px-1"
                  autoFocus
                  onKeyDown={(e) => e.key === "Enter" && saveClientRate()}
                />
                <select
                  value={clientRatePeriodDraft}
                  onChange={(e) => setClientRatePeriodDraft(e.target.value)}
                  className="h-6 text-xs border border-gray-300 rounded px-1"
                >
                  <option value="hourly">hourly</option>
                  <option value="monthly">monthly</option>
                  <option value="annual">annual</option>
                </select>
                <button className="text-xs text-teal-600 hover:underline" onClick={saveClientRate}>Save</button>
                <button className="text-xs text-gray-400 hover:underline" onClick={() => setClientRateEdit(false)}>Cancel</button>
              </span>
            ) : (
              <span
                className="flex items-center gap-1 cursor-pointer hover:text-teal-600"
                onClick={() => {
                  setClientRateDraft(position.client_rate ? String(position.client_rate) : "");
                  setClientRatePeriodDraft(position.client_rate_period || "monthly");
                  setClientRateEdit(true);
                }}
                title="Set client rate"
              >
                💰 {position.client_rate
                  ? `Client rate: ${position.client_rate_currency || "USD"} ${position.client_rate}/${position.client_rate_period || "mo"}`
                  : "Set client rate"}
              </span>
            )}
          </div>
        </div>
        <div className="flex gap-2 shrink-0">
          {position.status === "open" && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => closeMutation.mutate()}
              disabled={closeMutation.isPending}
            >
              Mark Filled
            </Button>
          )}
        </div>
      </div>

      {/* JD Section */}
      <JdSection
        position={position}
        jdDocs={jdDocs}
        onOpenJdDialog={() => setJdDialogOpen(true)}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: AI Insights */}
        <div className="space-y-4">
          {talentBrief && (
            <Card className="bg-white border border-gray-200">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold text-gray-700">Talent Brief (AI)</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {Array.isArray(talentBrief.result_data.skills_required) && (
                  <div>
                    <p className="text-xs font-medium text-gray-500 mb-1">Required Skills</p>
                    <div className="flex flex-wrap gap-1">
                      {(talentBrief.result_data.skills_required as Array<{name: string; criticality: string}>)
                        .slice(0, 6)
                        .map((s, i) => (
                          <span key={i} className={`text-xs px-2 py-0.5 rounded-full ${s.criticality === "must" ? "bg-teal-100 text-teal-700" : "bg-gray-100 text-gray-600"}`}>
                            {s.name}
                          </span>
                        ))}
                    </div>
                  </div>
                )}
                {talentBrief.result_data.estimated_time_to_fill_days != null && (
                  <p className="text-xs text-gray-500">
                    Est. time to fill: <strong>{String(talentBrief.result_data.estimated_time_to_fill_days)} days</strong>
                  </p>
                )}
              </CardContent>
            </Card>
          )}

          {levelAdvisor && (
            <Card className="bg-white border border-gray-200">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold text-gray-700">Level Advisor (AI)</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-gray-500">
                  Recommended:{" "}
                  <strong className="text-gray-800 capitalize">
                    {String(levelAdvisor.result_data.recommended_level ?? "—")}
                  </strong>
                </p>
                {levelAdvisor.result_data.reasoning != null && (
                  <p className="text-xs text-gray-400 mt-1 line-clamp-3">{String(levelAdvisor.result_data.reasoning)}</p>
                )}
              </CardContent>
            </Card>
          )}

          {/* JD Reality Check */}
          {realityCheck ? (() => {
            const d = realityCheck.result_data;
            const nc = d.necessity_check as Record<string, unknown> ?? {};
            const svr = d.skills_vs_reality as Record<string, unknown> ?? {};
            const wa = d.workload_analysis as Record<string, unknown> ?? {};
            const isJustified = nc.is_hire_justified !== false;
            const priority = nc.priority as string ?? "medium";
            const jdRequires = svr.jd_requires as string[] ?? [];
            const alreadyHasSet = new Set((svr.team_already_has as string[] ?? []).map((s: string) => s.toLowerCase()));
            const questionableSet = new Set((svr.questionable_requirements as string[] ?? []).map((s: string) => s.toLowerCase()));
            const actuallyNeeded = svr.actually_needed as string[] ?? [];
            const suggestions = d.jd_improvement_suggestions as string[] ?? [];
            const conf = (realityCheck.confidence_score ?? 0) * 100;
            return (
              <Card className="bg-white border border-gray-200">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-semibold text-gray-700">JD Reality Check (AI)</CardTitle>
                    <span className="text-xs text-gray-400">Confidence: {Math.round(conf)}%</span>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  {/* Verdict */}
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
                    <blockquote className="border-l-2 border-rose-300 pl-2 text-xs text-gray-600 italic">
                      {String(d.reasoning)}
                    </blockquote>
                  )}

                  {/* Skills vs Reality table */}
                  {jdRequires.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-gray-600 mb-1.5">Skills vs Reality</p>
                      <div className="rounded-lg border border-gray-100 overflow-hidden">
                        <div className="grid grid-cols-2 text-[10px] font-medium text-gray-500 bg-gray-50 px-2 py-1">
                          <span>JD Requires</span>
                          <span>Reality</span>
                        </div>
                        {jdRequires.slice(0, 6).map((skill, i) => {
                          const lower = skill.toLowerCase();
                          const has = alreadyHasSet.has(lower) || [...alreadyHasSet].some((h) => lower.includes(h) || h.includes(lower));
                          const odd = questionableSet.has(lower) || [...questionableSet].some((q) => lower.includes(q) || q.includes(lower));
                          return (
                            <div key={i} className={`grid grid-cols-2 text-xs px-2 py-1 ${i % 2 === 0 ? "bg-white" : "bg-gray-50/50"}`}>
                              <span className="text-gray-700 truncate pr-1">{skill}</span>
                              <span className={has ? "text-emerald-600" : odd ? "text-amber-600" : "text-gray-400"}>
                                {has ? "✅ team has" : odd ? "⚠️ questionable" : "—"}
                              </span>
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
                        {actuallyNeeded.slice(0, 6).map((s, i) => (
                          <span key={i} className="text-xs bg-rose-50 text-rose-700 px-1.5 py-0.5 rounded-full">{s}</span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Workload mismatches */}
                  {Array.isArray(wa.mismatches) && (wa.mismatches as string[]).length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-amber-700 mb-1">⚠️ JD vs Reality</p>
                      {(wa.mismatches as string[]).slice(0, 3).map((m, i) => (
                        <p key={i} className="text-xs text-gray-500">• {m}</p>
                      ))}
                    </div>
                  )}

                  {/* Necessity reasoning */}
                  {nc.reasoning != null && (
                    <p className="text-xs text-gray-500 border-t border-gray-100 pt-2">
                      <span className="font-medium text-gray-700">Necessity: </span>
                      {String(nc.reasoning)}
                    </p>
                  )}

                  {/* Alternative suggestions from necessity check */}
                  {Array.isArray(nc.alternative_suggestions) && (nc.alternative_suggestions as string[]).length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-gray-600 mb-0.5">Alternatives to consider</p>
                      {(nc.alternative_suggestions as string[]).slice(0, 2).map((s, i) => (
                        <p key={i} className="text-xs text-gray-500">• {s}</p>
                      ))}
                    </div>
                  )}

                  {/* JD improvement suggestions */}
                  {suggestions.length > 0 && (
                    <div className="border-t border-gray-100 pt-2">
                      <p className="text-xs font-medium text-gray-600 mb-1">JD Improvement Suggestions</p>
                      <ul className="text-xs text-gray-500 space-y-0.5">
                        {suggestions.slice(0, 4).map((s, i) => (
                          <li key={i} className="flex gap-1.5"><span className="text-teal-500 shrink-0">•</span>{s}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Re-run button */}
                  <Button
                    size="sm"
                    variant="outline"
                    className="w-full text-xs gap-1 mt-1"
                    onClick={handleRealityCheck}
                    disabled={runningRealityCheck}
                  >
                    {runningRealityCheck ? <><Loader2 className="w-3 h-3 animate-spin" /> Running...</> : "Re-run Reality Check"}
                  </Button>
                </CardContent>
              </Card>
            );
          })() : position.jd_document_id && (
            <Card className="bg-gray-50 border border-dashed border-gray-200">
              <CardContent className="p-4 text-center space-y-2">
                <p className="text-xs font-medium text-gray-600">JD Reality Check</p>
                <p className="text-xs text-gray-400">
                  Audits whether this role is needed given your current team and reports.
                  Best results with team members + weekly reports uploaded.
                </p>
                {realityCheckError && (
                  <p className="text-xs text-red-500">{realityCheckError}</p>
                )}
                <Button
                  size="sm"
                  variant="outline"
                  className="w-full text-xs gap-1"
                  onClick={handleRealityCheck}
                  disabled={runningRealityCheck}
                >
                  {runningRealityCheck ? <><Loader2 className="w-3 h-3 animate-spin" /> Running...</> : "Run JD Reality Check"}
                </Button>
              </CardContent>
            </Card>
          )}

          {!talentBrief && !levelAdvisor && !position.jd_document_id && (
            <Card className="bg-gray-50 border border-dashed border-gray-200">
              <CardContent className="p-4 text-center text-xs text-gray-400">
                Run AI Analysis (Mode A & C) on this position&apos;s JD to see insights here.
              </CardContent>
            </Card>
          )}
        </div>

        {/* Right: Candidates */}
        <div className="lg:col-span-2">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-base font-semibold text-gray-800">Candidates</h2>
            <Button
              className="bg-teal-600 hover:bg-teal-700 text-white gap-1.5"
              size="sm"
              onClick={() => setAddOpen(true)}
            >
              <Upload className="w-3.5 h-3.5" /> Add Candidate
            </Button>
          </div>

          {scoreError && (
            <div className="mb-3 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-600 flex items-center gap-1">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0" /> {scoreError}
            </div>
          )}

          {unscoredCount > 0 && position.jd_document_id && (
            <div className="mb-3 p-3 bg-blue-50 border border-blue-200 rounded-xl flex items-center justify-between gap-3">
              <p className="text-sm text-blue-700">
                💡 {unscoredCount} candidate{unscoredCount !== 1 ? "s have" : " has"} not been analyzed yet. AI will compare their resumes against the JD and score skills match, experience, and team fit.
              </p>
              <Button
                size="sm"
                className="bg-blue-600 hover:bg-blue-700 text-white gap-1.5 shrink-0"
                onClick={handleScoreAll}
                disabled={scoringAll}
              >
                {scoringAll ? (
                  <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Analyzing...</>
                ) : (
                  `Analyze ${unscoredCount} Candidate${unscoredCount !== 1 ? "s" : ""}`
                )}
              </Button>
            </div>
          )}
          {unscoredCount > 0 && !position.jd_document_id && (
            <div className="mb-3 p-3 bg-amber-50 border border-amber-200 rounded-xl text-sm text-amber-700 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" /> Link a JD to this position to enable AI candidate scoring.
            </div>
          )}

          {allCandidates.length === 0 ? (
            <div className="text-center py-16 border-2 border-dashed border-gray-200 rounded-xl text-gray-400">
              <UserRound className="w-10 h-10 mx-auto mb-3 opacity-40" />
              <p className="text-sm">No candidates yet.</p>
              <Button
                className="mt-3 bg-teal-600 hover:bg-teal-700 text-white"
                size="sm"
                onClick={() => setAddOpen(true)}
              >
                Add first candidate
              </Button>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-left text-xs text-gray-500 border-b border-gray-200">
                    <th className="py-2 px-4 font-medium w-8">#</th>
                    <th className="py-2 px-4 font-medium">Name</th>
                    <th className="py-2 px-4 font-medium">Score</th>
                    <th className="py-2 px-4 font-medium">Verdict</th>
                    <th className="py-2 px-4 font-medium">Skills Match</th>
                    <th className="py-2 px-4 font-medium">Experience</th>
                    <th className="py-2 px-4 font-medium">Margin</th>
                    <th className="py-2 px-4 font-medium">Status</th>
                    <th className="py-2 px-4 font-medium">Analyzed</th>
                    <th className="py-2 px-4 font-medium">Actions</th>
                    <th className="py-2 px-2 font-medium w-6"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {allCandidates.map((c, i) => (
                    <CandidateRow
                      key={c.id}
                      candidate={c}
                      rank={i + 1}
                      positionId={positionId}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <AddCandidateDialog
        positionId={positionId}
        resumeDocs={resumeDocs}
        open={addOpen}
        onClose={() => setAddOpen(false)}
      />

      <ReplaceJdDialog
        positionId={positionId}
        jdDocs={jdDocs}
        open={jdDialogOpen}
        onClose={() => setJdDialogOpen(false)}
      />
    </>
  );
}
