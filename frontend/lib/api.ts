export interface RoadmapItem {
  id: string;
  label: string;
  size: number;
  dominant_feature_area: string;
  avg_severity: number;
  avg_sentiment: number;
  high_churn_share: number;
  emerging: boolean;
  priority_score: number;
  rationale: string;
}

export interface FeatureArea {
  feature_area: string;
  count: number;
  avg_severity: number;
  avg_sentiment: number;
}

export interface AlertItem {
  id: string;
  cluster_id: string;
  severity: number;
  title: string;
  detail: string;
  channels: string[];
}

export interface Stats {
  total_tickets: number;
  noise_filtered: number;
  clusters: number;
  bugs: number;
  feature_requests: number;
  cache: { hits: number; misses: number; total: number; hit_rate: number };
}

const base = "/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${base}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export const fetcher = <T,>(path: string) => get<T>(path);

export const api = {
  analyze: () => fetch(`${base}/analyze`, { method: "POST" }).then((r) => r.json()),
  stats: () => get<Stats>("/stats"),
  roadmap: (top = 12) => get<RoadmapItem[]>(`/roadmap?top=${top}`),
  featureAreas: () => get<FeatureArea[]>("/feature-areas"),
  alerts: (limit = 12) => get<AlertItem[]>(`/alerts?limit=${limit}`),
};
