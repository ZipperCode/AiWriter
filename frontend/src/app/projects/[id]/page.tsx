"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { projectsApi, chaptersApi, entitiesApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ChapterTree } from "@/components/studio/chapter-tree";

export default function ProjectPage() {
  const params = useParams();
  const projectId = params.id as string;

  const { data: project } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => projectsApi.get(projectId),
  });

  const { data: chapters } = useQuery({
    queryKey: ["chapters", projectId],
    queryFn: () => chaptersApi.list(projectId),
  });

  const { data: entities } = useQuery({
    queryKey: ["entities", projectId],
    queryFn: () => entitiesApi.list(projectId),
  });

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">{project?.title || "Loading..."}</h2>
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader><CardTitle className="text-sm">Chapters</CardTitle></CardHeader>
          <CardContent><p className="text-2xl font-bold">{chapters?.length || 0}</p></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm">Entities</CardTitle></CardHeader>
          <CardContent><p className="text-2xl font-bold">{entities?.length || 0}</p></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm">Genre</CardTitle></CardHeader>
          <CardContent><p className="text-2xl font-bold">{project?.genre || "-"}</p></CardContent>
        </Card>
      </div>
      <div className="border rounded-lg h-96">
        <ChapterTree projectId={projectId} />
      </div>
    </div>
  );
}
