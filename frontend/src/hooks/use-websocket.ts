"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { createPipelineWS, type PipelineEvent } from "@/lib/ws";

export function usePipelineWS(jobRunId: string | null) {
  const [events, setEvents] = useState<PipelineEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    if (!jobRunId) return;
    const ws = createPipelineWS(jobRunId);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (e) => {
      const event: PipelineEvent = JSON.parse(e.data);
      setEvents((prev) => [...prev, event]);
    };

    return () => {
      ws.close();
      setConnected(false);
    };
  }, [jobRunId]);

  useEffect(() => {
    const cleanup = connect();
    return cleanup;
  }, [connect]);

  const reset = () => setEvents([]);

  return { events, connected, reset };
}
