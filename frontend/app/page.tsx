"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type AlertItem, type FeatureArea, type RoadmapItem, type Stats } from "@/lib/api";
import { Kpis } from "@/components/Kpis";
import { Roadmap } from "@/components/Roadmap";
import { AreaChart } from "@/components/AreaChart";
import { Alerts } from "@/components/Alerts";

export default function Page() {
  const [stats, setStats] = useState<Stats>();
  const [roadmap, setRoadmap] = useState<RoadmapItem[]>([]);
  const [areas, setAreas] = useState<FeatureArea[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      await api.analyze();
    } catch {
      /* analyze is best-effort */
    }
    try {
      const [s, r, a, al] = await Promise.all([
        api.stats(),
        api.roadmap(12),
        api.featureAreas(),
        api.alerts(12),
      ]);
      setStats(s);
      setRoadmap(r);
      setAreas(a);
      setAlerts(al);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <>
      <header>
        <h1>VibeCheck-AI</h1>
        <span className="badge">customer feedback → roadmap</span>
        <button className="reload" onClick={() => void load()}>
          {loading ? "Loading…" : "Refresh"}
        </button>
      </header>
      <div className="wrap">
        <Kpis stats={stats} />
        <div className="grid">
          <div>
            <Roadmap items={roadmap} />
          </div>
          <div>
            <AreaChart areas={areas} />
            <Alerts alerts={alerts} />
          </div>
        </div>
      </div>
    </>
  );
}
