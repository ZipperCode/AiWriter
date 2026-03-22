"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { chaptersApi } from "@/lib/api";
import { ChapterTree } from "@/components/studio/chapter-tree";
import { ContentViewer } from "@/components/studio/content-viewer";
import { PipelinePanel } from "@/components/studio/pipeline-panel";

export default function StudioPage() {
  const params = useParams();
  const projectId = params.id as string;
  const chapterId = params.chapterId as string;

  const { data: chapter } = useQuery({
    queryKey: ["chapter", chapterId],
    queryFn: () => chaptersApi.get(chapterId),
  });

  return (
    <div className="flex h-[calc(100vh-8rem)] -m-6">
      <div className="w-56 border-r">
        <ChapterTree projectId={projectId} activeChapterId={chapterId} />
      </div>
      <ContentViewer title={chapter?.title || "Loading..."} content={chapter?.summary || null} />
      <PipelinePanel chapterId={chapterId} />
    </div>
  );
}
