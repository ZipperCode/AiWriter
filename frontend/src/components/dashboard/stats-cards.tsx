"use client";

import { useQuery } from "@tanstack/react-query";
import { chaptersApi, entitiesApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BookOpen, Users, FileText, BarChart } from "lucide-react";

export function StatsCards({ projectId }: { projectId: string }) {
  const { data: chapters } = useQuery({
    queryKey: ["chapters", projectId],
    queryFn: () => chaptersApi.list(projectId),
  });
  const { data: entities } = useQuery({
    queryKey: ["entities", projectId],
    queryFn: () => entitiesApi.list(projectId),
  });

  const stats = [
    { label: "Chapters", value: chapters?.length || 0, icon: BookOpen },
    { label: "Final", value: chapters?.filter((c) => c.status === "final").length || 0, icon: FileText },
    { label: "Entities", value: entities?.length || 0, icon: Users },
    { label: "Characters", value: entities?.filter((e) => e.entity_type === "character").length || 0, icon: BarChart },
  ];

  return (
    <div className="grid gap-4 md:grid-cols-4">
      {stats.map((s) => (
        <Card key={s.label}>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">{s.label}</CardTitle>
            <s.icon className="h-4 w-4 text-gray-500" />
          </CardHeader>
          <CardContent><p className="text-2xl font-bold">{s.value}</p></CardContent>
        </Card>
      ))}
    </div>
  );
}
