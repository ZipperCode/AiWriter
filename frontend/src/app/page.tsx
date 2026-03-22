"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { projectsApi } from "@/lib/api";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function HomePage() {
  const { data: projects, isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });

  if (isLoading) return <div className="text-gray-500">Loading...</div>;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Projects</h2>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {projects?.map((p) => (
          <Link key={p.id} href={`/projects/${p.id}`}>
            <Card className="hover:border-blue-500 transition-colors cursor-pointer">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">{p.title}</CardTitle>
                  <Badge variant={p.status === "active" ? "default" : "secondary"}>
                    {p.status}
                  </Badge>
                </div>
                <CardDescription>{p.genre}</CardDescription>
              </CardHeader>
            </Card>
          </Link>
        ))}
        {projects?.length === 0 && (
          <p className="text-gray-500 col-span-full">No projects yet.</p>
        )}
      </div>
    </div>
  );
}
