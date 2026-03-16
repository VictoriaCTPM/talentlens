"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Clock, Users, FolderOpen } from "lucide-react";
import { getPipeline, getProjects } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent } from "@/components/ui/card";
import Link from "next/link";

// ── Helpers ───────────────────────────────────────────────────────────────────

function DaysOpenBadge({ days }: { days: number }) {
  if (days > 30)
    return (
      <span className="inline-flex items-center gap-1 text-red-600 font-semibold text-sm">
        <Clock className="w-3.5 h-3.5" />
        {days}d
      </span>
    );
  if (days > 14)
    return (
      <span className="inline-flex items-center gap-1 text-amber-600 font-semibold text-sm">
        <Clock className="w-3.5 h-3.5" />
        {days}d
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 text-gray-500 text-sm">
      <Clock className="w-3.5 h-3.5" />
      {days}d
    </span>
  );
}

function StatusLabelBadge({ label }: { label: string }) {
  if (label === "Critical")
    return <Badge className="bg-red-50 text-red-700 border border-red-200 hover:bg-red-50">Critical</Badge>;
  if (label === "Slow")
    return <Badge className="bg-amber-50 text-amber-700 border border-amber-200 hover:bg-amber-50">Slow</Badge>;
  return <Badge className="bg-teal-50 text-teal-700 border border-teal-200 hover:bg-teal-50">On Track</Badge>;
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function PipelinePage() {
  const { data: pipelineData, isLoading: pipelineLoading, error: pipelineError } = useQuery({
    queryKey: ["pipeline"],
    queryFn: getPipeline,
    refetchInterval: 30_000,
  });

  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: getProjects,
  });

  const positions = pipelineData ?? [];
  const projects = projectsData?.items ?? [];
  const activeProjects = projects.filter((p) => p.status === "active");
  const criticalPositions = positions.filter((p) => p.status_label === "Critical");

  if (pipelineLoading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400">
        Loading…
      </div>
    );
  }

  if (pipelineError) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
        Failed to load pipeline data. Make sure the backend is running on port 8000.
      </div>
    );
  }

  return (
    <>
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Pipeline Monitor</h1>
        <p className="text-gray-500 mt-1">
          {positions.length} open position{positions.length !== 1 ? "s" : ""} across{" "}
          {activeProjects.length} active project{activeProjects.length !== 1 ? "s" : ""}
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: "Open Positions", value: positions.length, icon: FolderOpen, color: "text-teal-600" },
          { label: "Active Projects", value: activeProjects.length, icon: FolderOpen, color: "text-blue-600" },
          { label: "Critical (>30d)", value: criticalPositions.length, icon: AlertTriangle, color: "text-red-500" },
          {
            label: "Total Candidates",
            value: positions.reduce((s, p) => s + p.candidates_count, 0),
            icon: Users,
            color: "text-purple-600",
          },
        ].map(({ label, value, icon: Icon, color }) => (
          <Card key={label} className="bg-white border border-gray-200">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <Icon className={`w-5 h-5 ${color}`} />
                <div>
                  <div className="text-2xl font-bold text-gray-900">{value}</div>
                  <div className="text-xs text-gray-500">{label}</div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Critical alert */}
      {criticalPositions.length > 0 && (
        <Alert className="mb-6 border-red-200 bg-red-50">
          <AlertTriangle className="h-4 w-4 text-red-600" />
          <AlertDescription className="text-red-700">
            <strong>{criticalPositions.length}</strong> position
            {criticalPositions.length !== 1 ? "s" : ""} open for more than 30 days:{" "}
            {criticalPositions.map((p) => p.title).join(", ")}
          </AlertDescription>
        </Alert>
      )}

      {/* Table */}
      {positions.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <FolderOpen className="w-12 h-12 mx-auto mb-3 opacity-40" />
          <p className="text-sm">No open positions in the pipeline.</p>
          <p className="text-xs mt-1">
            Create a project, upload a JD, and add a position to get started.
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="bg-gray-50 hover:bg-gray-50">
                <TableHead className="font-semibold text-gray-700">Role</TableHead>
                <TableHead className="font-semibold text-gray-700">Project</TableHead>
                <TableHead className="font-semibold text-gray-700">Client</TableHead>
                <TableHead className="font-semibold text-gray-700">Days Open</TableHead>
                <TableHead className="font-semibold text-gray-700">Candidates</TableHead>
                <TableHead className="font-semibold text-gray-700">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {positions.map((pos) => (
                <TableRow
                  key={pos.id}
                  className={pos.status_label === "Critical" ? "bg-red-50/30" : ""}
                >
                  <TableCell className="font-medium text-gray-900">
                    <Link
                      href={`/positions/${pos.id}`}
                      className="hover:text-teal-600 hover:underline"
                    >
                      {pos.title}
                    </Link>
                  </TableCell>
                  <TableCell className="text-gray-600">
                    <Link
                      href={`/projects/${pos.project_id}`}
                      className="hover:text-teal-600 hover:underline"
                    >
                      {pos.project_name}
                    </Link>
                  </TableCell>
                  <TableCell className="text-gray-600">{pos.client_name}</TableCell>
                  <TableCell>
                    <DaysOpenBadge days={pos.days_open} />
                  </TableCell>
                  <TableCell>
                    <span className="inline-flex items-center gap-1 text-sm text-gray-600">
                      <Users className="w-3.5 h-3.5" />
                      {pos.candidates_count}
                    </span>
                  </TableCell>
                  <TableCell>
                    <StatusLabelBadge label={pos.status_label} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </>
  );
}
