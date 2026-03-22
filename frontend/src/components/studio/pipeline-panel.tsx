"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Play, Loader2 } from "lucide-react";
import { pipelineApi } from "@/lib/api";
import { usePipelineWS } from "@/hooks/use-websocket";

interface PipelinePanelProps {
  chapterId: string;
}

export function PipelinePanel({ chapterId }: PipelinePanelProps) {
  const [jobRunId, setJobRunId] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const { events, connected } = usePipelineWS(jobRunId);

  const handleRun = async () => {
    try {
      setRunning(true);
      const result = await pipelineApi.run(chapterId);
      setJobRunId(result.job_run_id);
    } catch (err) {
      console.error("Pipeline run failed:", err);
      setRunning(false);
    }
  };

  const lastEvent = events[events.length - 1];
  const isDone = lastEvent?.event_type === "pipeline_complete" || lastEvent?.event_type === "pipeline_error";

  return (
    <div className="w-80 border-l flex flex-col">
      <div className="p-3 border-b flex items-center justify-between">
        <h3 className="font-semibold text-sm">Pipeline</h3>
        <Button size="sm" onClick={handleRun} disabled={running && !isDone}>
          {running && !isDone ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Play className="h-4 w-4 mr-1" />}
          Run
        </Button>
      </div>
      {connected && <Badge variant="outline" className="mx-3 mt-2 w-fit">Connected</Badge>}
      <ScrollArea className="flex-1 p-3">
        <div className="space-y-2">
          {events.map((e, i) => (
            <div key={i} className="text-xs border rounded p-2">
              <div className="flex items-center justify-between">
                <Badge variant={e.event_type === "agent_complete" ? "default" : e.event_type === "agent_error" ? "destructive" : "secondary"}>
                  {e.event_type}
                </Badge>
                <span className="text-gray-500">{e.agent_name}</span>
              </div>
              {e.data && Object.keys(e.data).length > 0 && (
                <pre className="mt-1 text-gray-500 overflow-auto">{JSON.stringify(e.data, null, 2)}</pre>
              )}
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
