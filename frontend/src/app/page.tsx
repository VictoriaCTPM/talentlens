"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import {
  Building2,
  Users,
  Clock,
  FolderOpen,
  Plus,
  ChevronRight,
} from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { getProjects, createProject, type Project } from "@/lib/api";

// ── Helpers ───────────────────────────────────────────────────────────────────

function statusDot(status: string) {
  return status === "active"
    ? "bg-emerald-500"
    : status === "paused"
    ? "bg-amber-400"
    : "bg-gray-400";
}

function daysSince(dateStr: string) {
  return Math.floor(
    (Date.now() - new Date(dateStr).getTime()) / 86_400_000
  );
}

// ── Project Card ──────────────────────────────────────────────────────────────

function ProjectCard({ project }: { project: Project }) {
  const days = daysSince(project.updated_at);

  return (
    <Link href={`/projects/${project.id}`}>
      <Card className="bg-white border border-gray-200 rounded-xl hover:shadow-md transition-shadow cursor-pointer h-full">
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span
                  className={`w-2 h-2 rounded-full shrink-0 ${statusDot(project.status)}`}
                />
                <h3 className="font-semibold text-[#111827] text-[15px] truncate">
                  {project.name}
                </h3>
              </div>
              <p className="text-sm text-[#6B7280]">{project.client_name}</p>
            </div>
            <ChevronRight className="w-4 h-4 text-gray-400 shrink-0 mt-0.5" />
          </div>
        </CardHeader>
        <CardContent>
          {project.description && (
            <p className="text-sm text-gray-500 mb-4 line-clamp-2">
              {project.description}
            </p>
          )}
          <div className="flex items-center gap-4 text-xs text-[#6B7280]">
            <span className="flex items-center gap-1">
              <Clock className="w-3.5 h-3.5" />
              {days === 0 ? "Today" : `${days}d ago`}
            </span>
            {project.team_members_count > 0 && (
              <span className="flex items-center gap-1">
                <Users className="w-3.5 h-3.5" />
                {project.team_members_count} team
              </span>
            )}
            {project.open_positions_count > 0 && (
              <span className="flex items-center gap-1">
                <FolderOpen className="w-3.5 h-3.5" />
                {project.open_positions_count} open
              </span>
            )}
            {project.total_candidates_count > 0 && (
              <span className="flex items-center gap-1">
                <Users className="w-3.5 h-3.5" />
                {project.total_candidates_count}
              </span>
            )}
          </div>
          <div className="mt-3 pt-3 border-t border-gray-100 flex items-center gap-2">
            <Badge
              variant="secondary"
              className={
                project.status === "active"
                  ? "bg-teal-50 text-teal-700 border-teal-200"
                  : project.status === "completed"
                  ? "bg-gray-100 text-gray-600"
                  : "bg-amber-50 text-amber-700 border-amber-200"
              }
            >
              {project.status}
            </Badge>
            {project.health_status === "at_risk" && (
              <Badge className="bg-red-50 text-red-600 border border-red-200 text-xs hover:bg-red-50">at risk</Badge>
            )}
            {project.health_status === "attention" && (
              <Badge className="bg-amber-50 text-amber-600 border border-amber-200 text-xs hover:bg-amber-50">needs attention</Badge>
            )}
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

// ── New Project Dialog ────────────────────────────────────────────────────────

function NewProjectDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [client, setClient] = useState("");
  const [desc, setDesc] = useState("");
  const [error, setError] = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      createProject({ name, client_name: client, description: desc }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      setName(""); setClient(""); setDesc(""); setError("");
      onClose();
    },
    onError: (e: Error) => setError(e.message),
  });

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>New Project</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <div>
            <label className="text-sm font-medium text-gray-700">
              Project Name *
            </label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Platform Team Expansion"
              className="mt-1"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-gray-700">
              Client Name *
            </label>
            <Input
              value={client}
              onChange={(e) => setClient(e.target.value)}
              placeholder="e.g. TechCorp"
              className="mt-1"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-gray-700">
              Description
            </label>
            <Input
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
              placeholder="Optional"
              className="mt-1"
            />
          </div>
          {error && <p className="text-sm text-red-500">{error}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button
              className="bg-teal-600 hover:bg-teal-700 text-white"
              disabled={!name || !client || mutation.isPending}
              onClick={() => mutation.mutate()}
            >
              {mutation.isPending ? "Creating…" : "Create Project"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [newOpen, setNewOpen] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ["projects"],
    queryFn: getProjects,
  });

  const projects = data?.items ?? [];
  const active = projects.filter((p) => p.status === "active");
  const completed = projects.filter((p) => p.status !== "active");
  const totalOpenPositions = projects.reduce((s, p) => s + (p.open_positions_count ?? 0), 0);
  const totalCandidates = projects.reduce((s, p) => s + (p.total_candidates_count ?? 0), 0);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400">
        Loading…
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
        Failed to load projects. Make sure the backend is running on port 8000.
      </div>
    );
  }

  return (
    <>
      {/* Stats bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {[
          {
            label: "Active Projects",
            value: active.length,
            icon: FolderOpen,
            color: "text-teal-600",
          },
          {
            label: "Total Projects",
            value: projects.length,
            icon: Building2,
            color: "text-blue-600",
          },
          {
            label: "Open Positions",
            value: totalOpenPositions,
            icon: Users,
            color: "text-purple-600",
          },
          {
            label: "Candidates",
            value: totalCandidates,
            icon: Clock,
            color: "text-gray-500",
          },
        ].map(({ label, value, icon: Icon, color }) => (
          <Card key={label} className="bg-white border border-gray-200">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <Icon className={`w-5 h-5 ${color}`} />
                <div>
                  <div className="text-2xl font-bold text-gray-900">
                    {value}
                  </div>
                  <div className="text-xs text-gray-500">{label}</div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Header + New button */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">
          Active Projects
        </h2>
        <Button
          className="bg-teal-600 hover:bg-teal-700 text-white gap-1.5"
          onClick={() => setNewOpen(true)}
        >
          <Plus className="w-4 h-4" />
          New Project
        </Button>
      </div>

      {/* Active projects grid */}
      {active.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <FolderOpen className="w-12 h-12 mx-auto mb-3 opacity-40" />
          <p className="text-sm">No active projects yet.</p>
          <Button
            className="mt-4 bg-teal-600 hover:bg-teal-700 text-white"
            onClick={() => setNewOpen(true)}
          >
            Create your first project
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 mb-8">
          {active.map((p) => (
            <ProjectCard key={p.id} project={p} />
          ))}
        </div>
      )}

      {/* Completed */}
      {completed.length > 0 && (
        <>
          <h2 className="text-lg font-semibold text-gray-900 mb-4 mt-4">
            Completed
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {completed.map((p) => (
              <ProjectCard key={p.id} project={p} />
            ))}
          </div>
        </>
      )}

      <NewProjectDialog open={newOpen} onClose={() => setNewOpen(false)} />
    </>
  );
}
