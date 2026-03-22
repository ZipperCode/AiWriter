"use client";

import { useQuery } from "@tanstack/react-query";
import { auditApi } from "@/lib/api";
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function AuditRadar({ projectId }: { projectId: string }) {
  const { data: dimData } = useQuery({
    queryKey: ["audit-dimensions"],
    queryFn: auditApi.dimensions,
  });

  const categories = dimData?.dimensions?.reduce(
    (acc, dim) => {
      if (!acc[dim.category]) acc[dim.category] = 0;
      acc[dim.category]++;
      return acc;
    },
    {} as Record<string, number>
  ) || {};

  const radarData = Object.entries(categories).map(([cat, count]) => ({
    category: cat,
    dimensions: count,
    fullMark: 10,
  }));

  return (
    <Card>
      <CardHeader><CardTitle className="text-sm">Audit Dimensions</CardTitle></CardHeader>
      <CardContent>
        {radarData.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <RadarChart data={radarData}>
              <PolarGrid />
              <PolarAngleAxis dataKey="category" />
              <PolarRadiusAxis />
              <Radar name="Dimensions" dataKey="dimensions" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.3} />
            </RadarChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-gray-500 text-sm">No audit data available.</p>
        )}
      </CardContent>
    </Card>
  );
}
