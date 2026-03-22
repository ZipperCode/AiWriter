"use client";

import { useParams } from "next/navigation";
import { StatsCards } from "@/components/dashboard/stats-cards";
import { AuditRadar } from "@/components/dashboard/audit-radar";
import { PacingChart } from "@/components/dashboard/pacing-chart";

export default function DashboardPage() {
  const params = useParams();
  const projectId = params.id as string;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Dashboard</h2>
      <StatsCards projectId={projectId} />
      <div className="grid gap-4 md:grid-cols-2">
        <AuditRadar projectId={projectId} />
        <PacingChart projectId={projectId} />
      </div>
    </div>
  );
}
