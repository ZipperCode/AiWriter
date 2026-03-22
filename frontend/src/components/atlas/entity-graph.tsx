"use client";

import { useCallback, useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { Entity, Relationship } from "@/lib/api";
import type { Node, Edge, NodeMouseHandler } from "@xyflow/react";

const ENTITY_COLORS: Record<string, string> = {
  character: "#3b82f6",
  location: "#10b981",
  faction: "#f59e0b",
  item: "#ef4444",
  concept: "#8b5cf6",
  power_system: "#ec4899",
};

interface EntityGraphProps {
  entities: Entity[];
  relationships: Relationship[];
  onNodeClick?: (entity: Entity) => void;
}

export function EntityGraph({ entities, relationships, onNodeClick }: EntityGraphProps) {
  const initialNodes: Node[] = useMemo(
    () =>
      entities.map((e, i) => ({
        id: e.id,
        position: { x: 150 + (i % 5) * 200, y: 100 + Math.floor(i / 5) * 150 },
        data: { label: e.name },
        style: {
          background: ENTITY_COLORS[e.entity_type] || "#6b7280",
          color: "white",
          border: "none",
          borderRadius: "8px",
          padding: "8px 16px",
          fontSize: "14px",
        },
      })),
    [entities]
  );

  const initialEdges: Edge[] = useMemo(
    () =>
      relationships.map((r) => ({
        id: r.id,
        source: r.source_entity_id,
        target: r.target_entity_id,
        label: r.relation_type,
        style: { stroke: "#94a3b8" },
        labelStyle: { fontSize: "11px", fill: "#64748b" },
      })),
    [relationships]
  );

  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);

  const handleNodeClick: NodeMouseHandler = useCallback(
    (_, node) => {
      const entity = entities.find((e) => e.id === node.id);
      if (entity && onNodeClick) onNodeClick(entity);
    },
    [entities, onNodeClick]
  );

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onNodeClick={handleNodeClick}
      fitView
    >
      <Background />
      <Controls />
      <MiniMap />
    </ReactFlow>
  );
}
