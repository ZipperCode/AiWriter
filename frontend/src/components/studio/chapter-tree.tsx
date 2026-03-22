"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { volumesApi, chaptersApi } from "@/lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface ChapterTreeProps {
  projectId: string;
  activeChapterId?: string;
}

export function ChapterTree({ projectId, activeChapterId }: ChapterTreeProps) {
  const { data: volumes } = useQuery({
    queryKey: ["volumes", projectId],
    queryFn: () => volumesApi.list(projectId),
  });

  const { data: chapters } = useQuery({
    queryKey: ["chapters", projectId],
    queryFn: () => chaptersApi.list(projectId),
  });

  const chaptersByVolume = (volumeId: string) =>
    chapters?.filter((c) => c.volume_id === volumeId)
      .sort((a, b) => a.sort_order - b.sort_order) || [];

  return (
    <ScrollArea className="h-full">
      <div className="p-3 space-y-4">
        {volumes?.sort((a, b) => a.sort_order - b.sort_order).map((vol) => (
          <div key={vol.id}>
            <h3 className="text-xs font-semibold text-gray-500 mb-1">{vol.title}</h3>
            <div className="space-y-0.5">
              {chaptersByVolume(vol.id).map((ch) => (
                <Link
                  key={ch.id}
                  href={`/projects/${projectId}/studio/${ch.id}`}
                  className={cn(
                    "block px-2 py-1.5 rounded text-sm",
                    ch.id === activeChapterId ? "bg-blue-600 text-white" : "hover:bg-gray-100"
                  )}
                >
                  <span>{ch.title}</span>
                  <Badge variant="outline" className="ml-2 text-xs">{ch.status}</Badge>
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
    </ScrollArea>
  );
}
