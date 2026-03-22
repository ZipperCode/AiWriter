"use client";

import { ScrollArea } from "@/components/ui/scroll-area";

interface ContentViewerProps {
  content: string | null;
  title: string;
}

export function ContentViewer({ content, title }: ContentViewerProps) {
  return (
    <div className="flex-1 flex flex-col">
      <div className="border-b px-4 py-2">
        <h2 className="font-semibold">{title}</h2>
      </div>
      <ScrollArea className="flex-1 p-4">
        {content ? (
          <div className="prose prose-sm max-w-none whitespace-pre-wrap">{content}</div>
        ) : (
          <p className="text-gray-500">No content yet.</p>
        )}
      </ScrollArea>
    </div>
  );
}
