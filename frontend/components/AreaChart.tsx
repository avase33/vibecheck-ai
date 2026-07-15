"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { FeatureArea } from "@/lib/api";

export function AreaChart({ areas }: { areas: FeatureArea[] }) {
  return (
    <div className="card">
      <h2>Feedback by feature area</h2>
      <div style={{ width: "100%", height: 220 }}>
        <ResponsiveContainer>
          <BarChart data={areas} margin={{ top: 8, right: 8, bottom: 8, left: -18 }}>
            <CartesianGrid stroke="#25304d" vertical={false} />
            <XAxis dataKey="feature_area" tick={{ fill: "#93a0bd", fontSize: 11 }} interval={0} angle={-25} height={60} textAnchor="end" />
            <YAxis tick={{ fill: "#93a0bd", fontSize: 11 }} />
            <Tooltip contentStyle={{ background: "#141b2e", border: "1px solid #25304d", color: "#e8ecf6" }} />
            <Bar dataKey="count" fill="#6c8cff" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
