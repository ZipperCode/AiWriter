"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { entitiesApi, type Entity } from "@/lib/api";
import { EntityGraph } from "@/components/atlas/entity-graph";
import { EntityDetail } from "@/components/atlas/entity-detail";

export default function AtlasPage() {
  const params = useParams();
  const projectId = params.id as string;
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);

  const { data: entities } = useQuery({
    queryKey: ["entities", projectId],
    queryFn: () => entitiesApi.list(projectId),
  });

  const { data: relationships } = useQuery({
    queryKey: ["relationships", projectId],
    queryFn: () => entitiesApi.relationships(projectId),
  });

  return (
    <div className="flex h-[calc(100vh-8rem)] -m-6">
      <div className="flex-1">
        <EntityGraph
          entities={entities || []}
          relationships={relationships || []}
          onNodeClick={setSelectedEntity}
        />
      </div>
      <EntityDetail entity={selectedEntity} />
    </div>
  );
}
