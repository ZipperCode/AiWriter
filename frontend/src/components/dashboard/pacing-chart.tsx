"use client";

import { useQuery } from "@tanstack/react-query";
import { pacingApi } from "@/lib/api";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const STRAND_COLORS: Record<string, string> = {
  quest: "#3b82f6",
  fire: "#ef4444",
  constellation: "#8b5cf6",
};

export function PacingChart({ projectId }: { projectId: string }) {
  const { data: pacing } = useQuery({
    queryKey: ["pacing", projectId],
    queryFn: () => pacingApi.analysis(projectId),
  });

  const chartData = pacing?.chapter_pacing?.map((ch, i) => ({
    chapter: `Ch${i + 1}`,
    emotion: ch.emotion_level,
    strand: ch.strand,
  })) || [];

  return (
    <Card>
      <CardHeader><CardTitle className="text-sm">Pacing & Emotion Curve</CardTitle></CardHeader>
      <CardContent>
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="chapter" />
              <YAxis domain={[0, 1]} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="emotion" stroke="#3b82f6" strokeWidth={2} dot={{ fill: "#3b82f6" }} />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-gray-500 text-sm">No pacing data available.</p>
        )}
        {pacing?.strand_ratios && (
          <div className="mt-4 flex gap-4">
            {Object.entries(pacing.strand_ratios).map(([strand, ratio]) => (
              <div key={strand} className="text-sm">
                <span className="inline-block w-3 h-3 rounded-full mr-1" style={{ background: STRAND_COLORS[strand] || "#6b7280" }} />
                {strand}: {(ratio * 100).toFixed(0)}%
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
