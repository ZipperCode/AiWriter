"use client";

import type { Entity } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";

interface EntityDetailProps {
  entity: Entity | null;
}

export function EntityDetail({ entity }: EntityDetailProps) {
  if (!entity) {
    return (
      <div className="w-80 border-l p-4 text-gray-500 text-sm">
        Click an entity to view details.
      </div>
    );
  }

  return (
    <div className="w-80 border-l">
      <ScrollArea className="h-full">
        <div className="p-4 space-y-4">
          <div>
            <h3 className="text-lg font-bold">{entity.name}</h3>
            <Badge>{entity.entity_type}</Badge>
          </div>
          <Separator />
          {entity.description && (
            <div>
              <h4 className="text-sm font-semibold mb-1">Description</h4>
              <p className="text-sm text-gray-500">{entity.description}</p>
            </div>
          )}
          {entity.attributes && Object.keys(entity.attributes).length > 0 && (
            <div>
              <h4 className="text-sm font-semibold mb-1">Attributes</h4>
              <Card>
                <CardContent className="p-3 text-xs">
                  <pre className="whitespace-pre-wrap">
                    {JSON.stringify(entity.attributes, null, 2)}
                  </pre>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
