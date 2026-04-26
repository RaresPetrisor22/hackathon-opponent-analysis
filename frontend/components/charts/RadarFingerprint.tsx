"use client";

import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
} from "recharts";

interface DataPoint {
  metric: string;
  value: number;
  fullMark: number;
}

interface Props {
  data: DataPoint[];
  color?: string;
  height?: number;
}

export function RadarFingerprint({ data, color = "#60a5fa", height = 280 }: Props) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <RadarChart data={data}>
        <PolarGrid stroke="#1a2747" />
        <PolarAngleAxis
          dataKey="metric"
          tick={{ fill: "#94a3b8", fontSize: 11, fontFamily: "JetBrains Mono" }}
        />
        <Radar
          name="Team"
          dataKey="value"
          stroke={color}
          fill={color}
          fillOpacity={0.18}
          strokeWidth={1.75}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}
