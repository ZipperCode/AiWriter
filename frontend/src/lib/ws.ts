const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export interface PipelineEvent {
  job_run_id: string;
  event_type: "agent_start" | "agent_progress" | "agent_complete" | "agent_error" | "pipeline_complete" | "pipeline_error";
  agent_name: string;
  data: Record<string, unknown>;
  timestamp: string;
}

export function createPipelineWS(jobRunId: string): WebSocket {
  return new WebSocket(`${WS_URL}/ws/${jobRunId}`);
}
