import type { Stats } from "@/lib/api";

export function Kpis({ stats }: { stats?: Stats }) {
  const cache = stats ? `${Math.round(stats.cache.hit_rate * 100)}%` : "—";
  const items: [string | number, string][] = [
    [stats?.total_tickets ?? "—", "tickets ingested"],
    [stats?.noise_filtered ?? "—", "noise filtered"],
    [stats?.clusters ?? "—", "topics discovered"],
    [stats?.bugs ?? "—", "bugs detected"],
    [cache, "LLM cache hit-rate"],
  ];
  return (
    <div className="kpis">
      {items.map(([n, l]) => (
        <div className="kpi" key={l}>
          <div className="n">{n}</div>
          <div className="l">{l}</div>
        </div>
      ))}
    </div>
  );
}
