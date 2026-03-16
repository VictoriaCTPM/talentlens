"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getCandidate,
  getCandidateTimeline,
  updateCandidate,
  updatePosition,
  scoreCandidate,
  getPosition,
  getAnalysisResult,
  type Candidate,
  type CandidateEvent,
  type Position,
  type AnalysisResult,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  ArrowLeft,
  Loader2,
  RotateCcw,
  User,
  CheckCircle,
  XCircle,
  AlertCircle,
  ChevronRight,
  Clock,
  Users,
  X,
} from "lucide-react";

// ── Helpers ───────────────────────────────────────────────────────────────────

const CANDIDATE_STATUSES = [
  { value: "new", label: "New", color: "bg-gray-100 text-gray-700" },
  { value: "screening", label: "Screening", color: "bg-blue-100 text-blue-700" },
  { value: "technical_interview", label: "Technical", color: "bg-purple-100 text-purple-700" },
  { value: "client_interview", label: "Client", color: "bg-violet-100 text-violet-700" },
  { value: "offer", label: "Offer", color: "bg-amber-100 text-amber-700" },
  { value: "hired", label: "Hired", color: "bg-emerald-100 text-emerald-700" },
  { value: "rejected", label: "Rejected", color: "bg-red-100 text-red-700" },
];

function statusColor(s: string) {
  return CANDIDATE_STATUSES.find((x) => x.value === s)?.color ?? "bg-gray-100 text-gray-600";
}
function statusLabel(s: string) {
  return CANDIDATE_STATUSES.find((x) => x.value === s)?.label ?? s;
}

function scoreBg(score: number) {
  if (score >= 80) return "bg-emerald-50";
  if (score >= 60) return "bg-amber-50";
  return "bg-red-50";
}
function scoreColor(score: number) {
  if (score >= 80) return "text-emerald-700";
  if (score >= 60) return "text-amber-700";
  return "text-red-700";
}

function verdictIcon(verdict: string) {
  const v = verdict.toLowerCase();
  if (v.includes("strong") || v.includes("hire") || v.includes("excellent"))
    return <CheckCircle className="w-4 h-4 text-emerald-500" />;
  if (v.includes("reject") || v.includes("no"))
    return <XCircle className="w-4 h-4 text-red-500" />;
  return <AlertCircle className="w-4 h-4 text-amber-500" />;
}

function fmtDate(d: string) {
  return new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function timelineIcon(eventType: string) {
  switch (eventType) {
    case "created": return <User className="w-3.5 h-3.5" />;
    case "status_change": return <ChevronRight className="w-3.5 h-3.5" />;
    case "scored": return <CheckCircle className="w-3.5 h-3.5" />;
    default: return <Clock className="w-3.5 h-3.5" />;
  }
}

function timelineLabel(event: CandidateEvent) {
  switch (event.event_type) {
    case "created":
      return `Candidate added`;
    case "status_change": {
      const from = event.event_data?.from as string | undefined;
      const to = event.event_data?.to as string | undefined;
      return `Status changed${from ? ` from ${statusLabel(from)}` : ""} → ${to ? statusLabel(to) : "unknown"}`;
    }
    case "scored": {
      const score = event.event_data?.score as number | undefined;
      const verdict = event.event_data?.verdict as string | undefined;
      return `AI scored: ${score != null ? Math.round(score) : "—"}${verdict ? ` — ${verdict.replace(/_/g, " ")}` : ""}`;
    }
    default:
      return event.event_type.replace(/_/g, " ");
  }
}

// ── Score Ring ────────────────────────────────────────────────────────────────

function ScoreRing({ score }: { score: number }) {
  const r = 40;
  const circ = 2 * Math.PI * r;
  const fill = (score / 100) * circ;

  const strokeColor =
    score >= 80 ? "#10b981" : score >= 60 ? "#f59e0b" : "#ef4444";

  return (
    <svg width="100" height="100" className="mx-auto">
      <circle cx="50" cy="50" r={r} fill="none" stroke="#e5e7eb" strokeWidth="8" />
      <circle
        cx="50"
        cy="50"
        r={r}
        fill="none"
        stroke={strokeColor}
        strokeWidth="8"
        strokeDasharray={`${fill} ${circ - fill}`}
        strokeLinecap="round"
        transform="rotate(-90 50 50)"
      />
      <text x="50" y="55" textAnchor="middle" fontSize="22" fontWeight="700" fill={strokeColor}>
        {Math.round(score)}
      </text>
    </svg>
  );
}

// ── Editable Field ────────────────────────────────────────────────────────────

function EditableField({
  label,
  value,
  icon,
  onSave,
  multiline = false,
  placeholder = "—",
}: {
  label: string;
  value: string | number | null | undefined;
  icon?: React.ReactNode;
  onSave: (v: string) => void;
  multiline?: boolean;
  placeholder?: string;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value != null ? String(value) : "");

  function commit() {
    setEditing(false);
    if (draft !== String(value ?? "")) onSave(draft);
  }

  if (editing) {
    return (
      <div className="space-y-1">
        <label className="text-xs font-medium text-gray-500 flex items-center gap-1">
          {icon}{label}
        </label>
        {multiline ? (
          <Textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commit}
            autoFocus
            rows={3}
            className="text-sm"
          />
        ) : (
          <Input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commit}
            onKeyDown={(e) => e.key === "Enter" && commit()}
            autoFocus
            className="h-8 text-sm"
          />
        )}
      </div>
    );
  }

  return (
    <div
      className="space-y-0.5 cursor-pointer group"
      onClick={() => { setDraft(value != null ? String(value) : ""); setEditing(true); }}
    >
      <label className="text-xs font-medium text-gray-500 flex items-center gap-1 cursor-pointer">
        {icon}{label}
      </label>
      <p className={`text-sm ${value != null && value !== "" ? "text-gray-900" : "text-gray-300"} group-hover:text-teal-600`}>
        {value != null && value !== "" ? String(value) : placeholder}
      </p>
    </div>
  );
}

// ── Margin Card ───────────────────────────────────────────────────────────────

function MarginCard({ candidate, position }: { candidate: Candidate; position?: Position }) {
  const qc = useQueryClient();
  const [candidateRateDraft, setCandidateRateDraft] = useState(
    candidate.candidate_rate != null ? String(candidate.candidate_rate) : ""
  );
  const [candidatePeriodDraft, setCandidatePeriodDraft] = useState(
    candidate.candidate_rate_period || "monthly"
  );
  const [clientRateDraft, setClientRateDraft] = useState(
    position?.client_rate != null ? String(position.client_rate) : ""
  );
  const [clientPeriodDraft, setClientPeriodDraft] = useState(
    position?.client_rate_period || "monthly"
  );
  const [saving, setSaving] = useState(false);

  const margin = candidate.margin as Record<string, unknown> | undefined;
  const marginPct = margin?.is_calculated ? Number(margin.margin_percentage) : null;
  const marginAbs = margin?.is_calculated ? Number(margin.margin_absolute) : null;
  const marginColor = marginPct == null ? "text-gray-400" : marginPct >= 40 ? "text-emerald-600" : marginPct >= 25 ? "text-amber-600" : "text-red-600";
  const marginBarColor = marginPct == null ? "bg-gray-200" : marginPct >= 40 ? "bg-emerald-400" : marginPct >= 25 ? "bg-amber-400" : "bg-red-400";

  async function handleSave() {
    setSaving(true);
    try {
      const promises = [];
      const newCandidateRate = candidateRateDraft ? parseFloat(candidateRateDraft) : undefined;
      promises.push(
        updateCandidate(candidate.id, {
          candidate_rate: newCandidateRate,
          candidate_rate_currency: "USD",
          candidate_rate_period: candidatePeriodDraft,
        })
      );
      if (position) {
        const newClientRate = clientRateDraft ? parseFloat(clientRateDraft) : undefined;
        promises.push(
          updatePosition(position.id, {
            client_rate: newClientRate,
            client_rate_currency: "USD",
            client_rate_period: clientPeriodDraft,
          })
        );
      }
      await Promise.all(promises);
      qc.invalidateQueries({ queryKey: ["candidate", candidate.id] });
      if (position) qc.invalidateQueries({ queryKey: ["position", position.id] });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold text-gray-700">Margin Calculator</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="space-y-2">
          <div>
            <label className="text-xs font-medium text-gray-500">Client Rate</label>
            <p className="text-xs text-gray-400 mb-1">Set at position level</p>
            <div className="flex gap-1.5">
              <Input
                value={clientRateDraft}
                onChange={(e) => setClientRateDraft(e.target.value)}
                placeholder="0"
                className="h-7 text-sm flex-1"
                type="number"
                disabled={!position}
              />
              <select
                value={clientPeriodDraft}
                onChange={(e) => setClientPeriodDraft(e.target.value)}
                className="h-7 text-xs border border-gray-300 rounded px-1"
                disabled={!position}
              >
                <option value="hourly">hourly</option>
                <option value="monthly">monthly</option>
                <option value="annual">annual</option>
              </select>
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500">Candidate Rate</label>
            <div className="flex gap-1.5 mt-1">
              <Input
                value={candidateRateDraft}
                onChange={(e) => setCandidateRateDraft(e.target.value)}
                placeholder="0"
                className="h-7 text-sm flex-1"
                type="number"
              />
              <select
                value={candidatePeriodDraft}
                onChange={(e) => setCandidatePeriodDraft(e.target.value)}
                className="h-7 text-xs border border-gray-300 rounded px-1"
              >
                <option value="hourly">hourly</option>
                <option value="monthly">monthly</option>
                <option value="annual">annual</option>
              </select>
            </div>
          </div>
        </div>

        <Button
          size="sm"
          className="bg-teal-600 hover:bg-teal-700 text-white w-full"
          onClick={handleSave}
          disabled={saving}
        >
          {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Save Rates"}
        </Button>

        {margin?.is_calculated === true && (
          <div className="pt-2 border-t border-gray-100">
            <div className="flex justify-between items-baseline mb-1">
              <span className="text-xs text-gray-500">Margin</span>
              <span className={`text-base font-bold ${marginColor}`}>{marginPct}%</span>
            </div>
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden mb-1">
              <div
                className={`h-full rounded-full ${marginBarColor}`}
                style={{ width: `${Math.min(Math.max(marginPct ?? 0, 0), 100)}%` }}
              />
            </div>
            <div className="flex justify-between text-xs text-gray-400">
              <span>Absolute: {String(margin.currency ?? "")} {marginAbs?.toLocaleString()}/mo</span>
              <span>{marginPct != null && marginPct >= 40 ? "Healthy" : marginPct != null && marginPct >= 25 ? "Tight" : "Low"}</span>
            </div>
            <div className="text-xs text-gray-400 mt-0.5">
              Client: {Number(margin.client_rate_monthly ?? 0).toLocaleString()} · Candidate: {Number(margin.candidate_rate_monthly ?? 0).toLocaleString()} /mo
            </div>
          </div>
        )}

        {margin && margin.is_calculated === false && margin.missing ? (
          <p className="text-xs text-gray-400 pt-1">
            Missing: {String(margin.missing).replace("_", " ")} — enter rates above to compute margin.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function CandidateProfile() {
  const params = useParams();
  const router = useRouter();
  const qc = useQueryClient();
  const candidateId = Number(params.id);

  const { data: candidate, isLoading, error } = useQuery({
    queryKey: ["candidate", candidateId],
    queryFn: () => getCandidate(candidateId),
    enabled: !isNaN(candidateId),
  });

  const { data: timeline = [] } = useQuery({
    queryKey: ["candidate-timeline", candidateId],
    queryFn: () => getCandidateTimeline(candidateId),
    enabled: !isNaN(candidateId),
  });

  const { data: position } = useQuery({
    queryKey: ["position", candidate?.position_id],
    queryFn: () => getPosition(candidate!.position_id),
    enabled: !!candidate?.position_id,
  });

  const { data: analysisResult } = useQuery({
    queryKey: ["analysis-result", candidate?.ai_analysis_id],
    queryFn: () => getAnalysisResult(candidate!.ai_analysis_id!),
    enabled: !!candidate?.ai_analysis_id,
  });

  const [scoring, setScoring] = useState(false);
  const [scoreErr, setScoreErr] = useState("");
  const [showHireConfirm, setShowHireConfirm] = useState(false);
  const [pendingHireStatus, setPendingHireStatus] = useState<string | null>(null);
  const [newTeamMemberId, setNewTeamMemberId] = useState<number | null>(null);

  const updateMutation = useMutation({
    mutationFn: (data: Parameters<typeof updateCandidate>[1]) =>
      updateCandidate(candidateId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["candidate", candidateId] }),
  });

  function handleStatusChange(newStatus: string) {
    if (newStatus === "hired") {
      setPendingHireStatus(newStatus);
      setShowHireConfirm(true);
      return;
    }
    updateMutation.mutate({ status: newStatus });
  }

  async function confirmHire() {
    setShowHireConfirm(false);
    if (!pendingHireStatus) return;
    try {
      const updated = await updateCandidate(candidateId, { status: pendingHireStatus });
      qc.invalidateQueries({ queryKey: ["candidate", candidateId] });
      qc.invalidateQueries({ queryKey: ["candidate-timeline", candidateId] });
      if (updated.team_member_id) {
        setNewTeamMemberId(updated.team_member_id);
      }
    } catch {
      // mutation errors surfaced via updateMutation normally; here just refresh
      qc.invalidateQueries({ queryKey: ["candidate", candidateId] });
    }
    setPendingHireStatus(null);
  }

  async function handleScore() {
    setScoreErr("");
    setScoring(true);
    try {
      await scoreCandidate(candidateId);
      qc.invalidateQueries({ queryKey: ["candidate", candidateId] });
      qc.invalidateQueries({ queryKey: ["candidate-timeline", candidateId] });
    } catch (e: unknown) {
      setScoreErr(e instanceof Error ? e.message : "Scoring failed");
    } finally {
      setScoring(false);
    }
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-teal-500" />
      </div>
    );
  }

  if (error || !candidate) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-3 text-gray-500">
        <p>Candidate not found.</p>
        <Button variant="outline" onClick={() => router.back()}>Go back</Button>
      </div>
    );
  }

  const analysisReasoning = typeof analysisResult?.result_data?.reasoning === "string"
    ? (analysisResult.result_data.reasoning as string)
    : null;

  return (
    <>
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500">
        {position?.project_id ? (
          <Link href={`/projects/${position.project_id}`} className="hover:text-teal-600">Project</Link>
        ) : (
          <Link href="/" className="hover:text-teal-600">Dashboard</Link>
        )}
        <span>/</span>
        <Link href={`/positions/${candidate.position_id}`} className="hover:text-teal-600">Position</Link>
        <span>/</span>
        <span className="text-gray-900 font-medium">{candidate.name}</span>
      </div>

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.back()}
            className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-xl font-bold text-gray-900">{candidate.name}</h1>
            {candidate.location && (
              <p className="text-sm text-gray-500">{candidate.location}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {candidate.status === "hired" && candidate.team_member_id ? (
            <div className="flex items-center gap-2">
              <Badge className="bg-emerald-100 text-emerald-800 border-emerald-200">Hired</Badge>
              <button
                onClick={() => router.push(`/team/${candidate.team_member_id}`)}
                className="text-xs text-teal-600 hover:underline font-medium"
              >
                View team profile →
              </button>
            </div>
          ) : (
            <Select
              value={candidate.status}
              onValueChange={(v) => v && handleStatusChange(v)}
            >
              <SelectTrigger className="h-8 text-xs w-32 border-gray-200">
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
          )}
          <Button
            size="sm"
            variant="outline"
            onClick={handleScore}
            disabled={scoring || !candidate.resume_document_id}
            title={!candidate.resume_document_id ? "No resume uploaded" : "Re-run AI analysis"}
            className="gap-1.5 text-teal-700 border-teal-200 hover:bg-teal-50"
          >
            {scoring ? (
              <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Analyzing...</>
            ) : (
              <><RotateCcw className="w-3.5 h-3.5" /> Re-analyze</>
            )}
          </Button>
        </div>
      </div>

      {scoreErr && (
        <div className="p-2 bg-red-50 border border-red-200 rounded text-xs text-red-600">{scoreErr}</div>
      )}

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">

        {/* Left 60%: AI + Info */}
        <div className="lg:col-span-3 space-y-4">

          {/* AI Score Card */}
          {candidate.ai_score != null ? (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold text-gray-700">AI Analysis</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center gap-6">
                  <div className="text-center">
                    <ScoreRing score={candidate.ai_score} />
                    <p className={`text-xs font-medium mt-1 ${scoreColor(candidate.ai_score)}`}>Overall Score</p>
                  </div>
                  <div className="flex-1 space-y-3">
                    {candidate.ai_verdict && (
                      <div className="flex items-center gap-2">
                        {verdictIcon(candidate.ai_verdict)}
                        <span className="text-sm font-medium text-gray-800 capitalize">
                          {candidate.ai_verdict.replace(/_/g, " ")}
                        </span>
                      </div>
                    )}
                    {candidate.skill_match_score != null && (
                      <div className="space-y-1">
                        <div className="flex justify-between text-xs text-gray-500">
                          <span>Skills Match</span>
                          <span className="font-medium">{Math.round(candidate.skill_match_score)}%</span>
                        </div>
                        <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${candidate.skill_match_score >= 70 ? "bg-emerald-400" : candidate.skill_match_score >= 50 ? "bg-amber-400" : "bg-red-400"}`}
                            style={{ width: `${Math.min(candidate.skill_match_score, 100)}%` }}
                          />
                        </div>
                      </div>
                    )}
                    {candidate.scored_at && (
                      <p className="text-xs text-gray-400">Analyzed {fmtDate(candidate.scored_at)}</p>
                    )}
                  </div>
                </div>

                {/* Reasoning */}
                {analysisReasoning ? (
                  <div className="bg-gray-50 rounded-lg p-3 border-l-3 border-gray-300">
                    <p className="text-xs font-medium text-gray-500 mb-1">AI Reasoning</p>
                    <p className="text-sm text-gray-600 italic leading-relaxed">
                      &ldquo;{analysisReasoning}&rdquo;
                    </p>
                  </div>
                ) : null}

                {/* Key Arguments */}
                {Array.isArray(analysisResult?.result_data?.key_arguments) && (analysisResult!.result_data.key_arguments as Array<{point: string; evidence: string; impact: string}>).length > 0 ? (
                  <div>
                    <p className="text-xs font-medium text-gray-500 mb-2">Key Arguments</p>
                    <ul className="space-y-1.5">
                      {(analysisResult!.result_data.key_arguments as Array<{point: string; evidence: string; impact: string}>).map((arg, i) => (
                        <li key={i} className="flex gap-2 text-sm">
                          <span className="shrink-0 mt-0.5">
                            {arg.impact === "positive" ? "✅" : arg.impact === "negative" ? "❌" : "⚠️"}
                          </span>
                          <div>
                            <span className="text-gray-800">{arg.point}</span>
                            {arg.evidence ? <span className="text-xs text-gray-400 block">{arg.evidence}</span> : null}
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                {/* Re-analyze warning */}
                {(candidate.interview_notes || candidate.client_feedback) && candidate.scored_at && (
                  <div className="bg-amber-50 border border-amber-200 rounded-lg p-2.5 text-xs text-amber-700 flex items-start gap-1.5">
                    <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                    <span>Re-analyze to include all available data (interview notes / client feedback may not be reflected in current score).</span>
                  </div>
                )}
              </CardContent>
            </Card>
          ) : (
            <Card className="border-dashed bg-gray-50">
              <CardContent className="p-4 text-center text-sm text-gray-400 space-y-2">
                <p>No AI analysis yet.</p>
                {candidate.resume_document_id ? (
                  <Button size="sm" className="bg-teal-600 hover:bg-teal-700 text-white" onClick={handleScore} disabled={scoring}>
                    {scoring ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Run AI Analysis"}
                  </Button>
                ) : (
                  <p className="text-xs text-amber-600">Upload a resume to enable AI scoring.</p>
                )}
              </CardContent>
            </Card>
          )}

          {/* Profile Details */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold text-gray-700">Profile</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4">
                <EditableField
                  label="Full Name"
                  value={candidate.name}
                  icon={<User className="w-3 h-3" />}
                  onSave={(v) => updateMutation.mutate({ name: v })}
                />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right 40%: Notes */}
        <div className="lg:col-span-2 space-y-4">

          <MarginCard candidate={candidate} position={position} />

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold text-gray-700">Recruiter Notes</CardTitle>
            </CardHeader>
            <CardContent>
              <EditableField
                label="Internal notes"
                value={candidate.recruiter_notes}
                onSave={(v) => updateMutation.mutate({ recruiter_notes: v })}
                multiline
                placeholder="Click to add notes…"
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold text-gray-700">Interview Notes</CardTitle>
            </CardHeader>
            <CardContent>
              <EditableField
                label="Notes from interviews"
                value={candidate.interview_notes}
                onSave={(v) => updateMutation.mutate({ interview_notes: v })}
                multiline
                placeholder="Click to add notes…"
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold text-gray-700">Client Feedback</CardTitle>
            </CardHeader>
            <CardContent>
              <EditableField
                label="Feedback from client"
                value={candidate.client_feedback}
                onSave={(v) => updateMutation.mutate({ client_feedback: v })}
                multiline
                placeholder="Click to add feedback…"
              />
            </CardContent>
          </Card>

          {candidate.status === "rejected" && (
            <Card className="border-red-100">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold text-red-600">Rejection Reason</CardTitle>
              </CardHeader>
              <CardContent>
                <EditableField
                  label="Why rejected"
                  value={candidate.rejection_reason}
                  onSave={(v) => updateMutation.mutate({ rejection_reason: v })}
                  multiline
                  placeholder="Click to add reason…"
                />
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Timeline */}
      {timeline.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-gray-700">Activity Timeline</CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="relative border-l border-gray-200 space-y-4 ml-2">
              {timeline.map((event) => (
                <li key={event.id} className="ml-5">
                  <span className="absolute -left-2.5 flex items-center justify-center w-5 h-5 bg-white border border-gray-200 rounded-full text-gray-400">
                    {timelineIcon(event.event_type)}
                  </span>
                  <div className="flex items-baseline justify-between">
                    <p className="text-sm text-gray-700">{timelineLabel(event)}</p>
                    <time className="text-xs text-gray-400 ml-3 shrink-0">{fmtDate(event.created_at)}</time>
                  </div>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      )}
    </div>

    {/* Hire confirmation dialog */}

    <Dialog open={showHireConfirm} onOpenChange={setShowHireConfirm}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Confirm Hire</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <p className="text-sm text-gray-600">
            This will mark <strong>{candidate.name}</strong> as hired
            {position ? <> for <strong>{position.title}</strong></> : null} and automatically
            add them to the project team.
          </p>
          <div className="bg-teal-50 border border-teal-200 rounded-lg p-3 text-sm">
            <p className="font-medium text-teal-800">What happens next:</p>
            <ul className="mt-1 text-teal-700 space-y-1">
              <li>• A new team member profile will be created</li>
              <li>• Their resume and skills will be transferred</li>
              <li>• The position will be marked as filled</li>
              <li>• You can set their start date in the Team tab</li>
            </ul>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setShowHireConfirm(false)}>
              Cancel
            </Button>
            <Button
              className="bg-teal-600 hover:bg-teal-700 text-white"
              onClick={confirmHire}
            >
              Confirm Hire
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>

    {/* Success toast after hire */}
    {newTeamMemberId && (
      <div className="fixed bottom-4 right-4 bg-white border border-teal-200 rounded-lg shadow-lg p-4 max-w-sm z-50">
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 bg-teal-100 rounded-full flex items-center justify-center shrink-0">
            <Users className="w-4 h-4 text-teal-600" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-medium text-gray-900 text-sm">{candidate.name} added to team</p>
            <p className="text-xs text-gray-500 mt-0.5">
              Team member profile created{position ? ` · ${position.title}` : ""}
            </p>
            <button
              onClick={() => router.push(`/team/${newTeamMemberId}`)}
              className="text-xs text-teal-600 hover:text-teal-700 font-medium mt-1.5 inline-block"
            >
              View team profile →
            </button>
          </div>
          <button
            onClick={() => setNewTeamMemberId(null)}
            className="text-gray-400 hover:text-gray-500 shrink-0"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
    )}
    </>
  );
}
