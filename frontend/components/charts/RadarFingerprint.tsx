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

export function RadarFingerprint({ data, color = "#00ff88", height = 280 }: Props) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <RadarChart data={data}>
        <PolarGrid stroke="#1c2333" />
        <PolarAngleAxis
          dataKey="metric"
          tick={{ fill: "#9ca3af", fontSize: 11, fontFamily: "JetBrains Mono" }}
        />
        <Radar
          name="Team"
          dataKey="value"
          stroke={color}
          fill={color}
          fillOpacity={0.15}
          strokeWidth={1.5}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}
